#!/usr/bin/env python3

"""
The MIT License (MIT)

Copyright (c) 2018 Colum McGaley <colum.mcgaley@fastmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import tqdm
import halo
from loguru import logger
import requests
from bs4 import BeautifulSoup
import re
import os
import argparse
import sys
import getpass
import json
import cgi
import datetime
from urllib.parse import unquote


D2L_BASEURL = "https://mycourses.rit.edu/"

# Not sure if this is unique to me, or just unique to RIT's tenant
OU = 6605

logger.remove()
logger.add(sys.stderr, level="INFO")

# basically, mkdir -p /blah/blah/blah
def mkdir_recursive(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        logger.error("Exception: {}".format(e))
        exit(1)


def get_xfrs_token(page_html):
    """
    Method to parse a D2L page to find the XSRF.Token. The token is returned as a string
    :param page_html:
    :return:
    """
    soup = BeautifulSoup(page_html, "html.parser")
    # TODO Loop over all of them, as the location might change
    xsrf = str(soup.findAll("script")[0]).splitlines()
    token = None

    for line in xsrf:
        if "XSRF.Token" in line:  #
            line_soup = re.findall("'(.*?)'", line)
            # We can also find our User.ID in this line as well
            for i in range(0, len(line_soup)):
                if line_soup[i] == 'XSRF.Token':
                    token = line_soup[i + 1]
                    break

    if token is None:
        logger.critical("Cannot find XSRF.Token. Code might have changed")
        exit(1)
    logger.debug("Found XSRF.Token. It's {}".format(token))

    return token


def safeFilePath(path):
    ## Fucking unicode
    path = ''.join([i if ord(i) < 128 else ' ' for i in path])

    bad = ["<", ">", ":", "|", "?", "*", " / ", " \ "]
    for char in bad:
        path = path.replace(char, " ")
    return path


def download(rqs, furl, path, level=3):
    if furl[0:4] != 'http':
        furl = "{}/{}".format(D2L_BASEURL, furl)

    file = rqs.get(furl, stream=True, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:64.0) Gecko/20100101 Firefox/64.0"
    })

    if file.status_code == 302:  # D2L, you don't fucking redirect a 404/403 error.
        logger.error("Requested file is Not Found or Forbidden")

    if not os.path.isdir(safeFilePath(path)):
        # logger.info("Directory does not exist.")
        logger.debug(safeFilePath(path))
        mkdir_recursive(safeFilePath(path))

    try:
        name = furl.split('?')[0].split('/')[-1]

        if name == "DirectFileTopicDownload":
            name = file.headers['Content-Disposition'].split(';')[-1].split('=')[-1][1:-1]

        path += "/" + safeFilePath(name)
        with open(unquote(path), 'wb') as f:
            for chunk in tqdm.tqdm(file.iter_content(chunk_size=1024), desc="Downloading {}".format(name),
                                   position=level, unit="kb"):  # is it kb or b?

                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()
    except Exception as e:
        logger.exception("Exception caught during file download. {}", str(e))


if __name__ == "__main__":

    #
    # Set up Required Variables to Auth to MyCourses
    #

    if sys.version_info[0] < 3:
        print("I need python 3+")
        exit()

    parser = argparse.ArgumentParser(description='Downloads all course contents from MyCourses')
    parser.add_argument('-u', help='Your RIT Username that you use for MyCourses')
    parser.add_argument('-d', help='The directory where the files will be downloaded')

    args = parser.parse_args()

    if args.u is None:
        args.u = input("RIT Username: ")

    password = getpass.getpass("RIT Password: ")

    if args.d is None:
        args.d = input("Enter download directory: ")
        if not args.d:
            args.d = os.path.join(os.getcwd(),"MyCoursesDownloaderOutput")

    workingDirectory = os.path.join(os.getcwd(), args.d)

    if not os.path.exists(workingDirectory):
        logger.warning("Directory does not exist. Creating")
        mkdir_recursive(workingDirectory)

    URLS = []  # [("22222", "PLOS.140"), ("11111", "NSSA.220")]

    #
    # Start the Session
    #
    with halo.Halo(text="Logging in to MyCourses", spinner="dots") as progress:

        session = requests.Session()
        # Log in. Now with Shibboleth support!
        r = session.get(
            D2L_BASEURL + '/Shibboleth.sso/Login?entityID=https://shibboleth.main.ad.rit.edu/idp/shibboleth&target=https%3A%2F%2Fmycourses.rit.edu%2Fd2l%2FshibbolethSSO%2Flogin.d2l',
            allow_redirects=True)

        rs = session.post(r.url, data={
            'j_username': args.u,
            'j_password': password,
            '_eventId_proceed': ''
        })
        if rs.status_code > 399:
            progress.clear()
            logger.warning("Shibboleth rejected your username and/or password.")
            exit()

        # 06/11/16 - Fuck. D2l is much more secure that RIT's Shibboleth implementations
        # Ok. So. I hit Shibboleth.sso/SAML2/POST, and in my browser I get two 302 redirects and end up at lelogin.d2.
        # Here, I'm getting bumped to a 500 error page (Which is fucking stupid D2l. Dont 302 error pages)
        # after the initial hit.

        # 06/12/16 - Ok, so it wasn't a cookie issue. The issue here is that Shibboleth was returning an unicode encoded
        # RelayState, which FireFox and Chrome handle correctly. The problem was that Requests/urllib3 does not decode
        # it, and was passing the raw unicoded string onto D2l which was causing it to choke.

        try:
            dta = {
                # TODO Make this dynamic and read the data from the response one I figure out how to decode the stuff. .decode() does not work
                "RelayState": "https://mycourses.rit.edu/d2l/shibbolethSSO/login.d2l",
                "SAMLResponse": re.search('(<input type="hidden" name="SAMLResponse" value=").*("/>)', rs.text).group(
                    0).replace('<input type="hidden" name="SAMLResponse" value="', '').replace('"/>', '')
            }
        # Soooo it seems that shibboleth might not return the right code on password error
        except Exception:
            progress.clear()
            logger.warning("Shibboleth rejected your username and/or password.")
            exit()

        rq = session.post(D2L_BASEURL + "/Shibboleth.sso/SAML2/POST", data=dta, allow_redirects=True)
        session.get(D2L_BASEURL + "/d2l/lp/auth/login/ProcessLoginActions.d2l")

    logger.info("Successfully logged into MyCourses")

    with halo.Halo(text="Discovering Courses", spinner="dots") as progress:

        # We need to get the XSRF.Token to move forward
        bph = session.get("{}/d2l/le/manageCourses/search/6605".format(D2L_BASEURL))
        if bph.status_code != 200:
            logger.error("Course Query failed. Invalid response code! Expected 200, got {}", bph.status_code)
            exit(1)

        token = get_xfrs_token(bph.text)
        now = datetime.datetime.now()
        query_data = {
            "gridPartialInfo$_type": "D2L.LP.Web.UI.Desktop.Controls.GridPartialArgs",
            "gridPartialInfo$SortingInfo$SortField": "OrgUnitName",
            "gridPartialInfo$SortingInfo$SortDirection": "0",
            "gridPartialInfo$NumericPagingInfo$PageNumber": "1",
            "gridPartialInfo$NumericPagingInfo$PageSize": "100",
            "searchTerm": "",
            "status": "-1",
            "toStartDate$Year": str(now.year),
            "toStartDate$Month": str(now.month),
            "toStartDate$Day": str(now.day),
            "toStartDate$Hour": "21",
            "toStartDate$Minute": "0",
            "toStartDate$Second": "0",
            "fromStartDate$Year": str(now.year),
            "fromStartDate$Month": str(now.month),
            "fromStartDate$Day": str(now.day),
            "fromStartDate$Hour": "21",
            "fromStartDate$Minute": "0",
            "fromStartDate$Second": "0",
            "toEndDate$Year": str(now.year),
            "toEndDate$Month": str(now.month),
            "toEndDate$Day": str(now.day),
            "toEndDate$Hour": "21",
            "toEndDate$Minute": "0",
            "toEndDate$Second": "0",
            "fromEndDate$Year": str(now.year),
            "fromEndDate$Month": str(now.month),
            "fromEndDate$Day": str(now.day),
            "fromEndDate$Hour": "21",
            "fromEndDate$Minute": "0",
            "fromEndDate$Second": "0",
            "hasToStartDate": "False",
            "hasFromStartDate": "False",
            "hasToEndDate": "False",
            "hasFromEndDate": "False",
            "filtersFormId$Value": "d2l_1_0_180",  # Not sure what this is
            "_d2l_prc$headingLevel": "2",
            "_d2l_prc$scope": "",
            "_d2l_prc$childScopeCounters": "filtersData:0;FromStartDate:0;ToStartDate:0;FromEndDate:0;ToEndDate:0",
            "_d2l_prc$hasActiveForm": "false",
            "filtersData$roleIds": "",
            "filtersData$semesterId": "All",
            "filtersData$departmentId": "All",
            "isXhr": "true",
            "requestId": "2",
            "d2l_referrer": token,
        }

        courses = session.post("{base}/d2l/le/manageCourses/search/{ou}/GridReloadPartial".format(base=D2L_BASEURL, ou=OU), data=query_data)

        # Fuck you D2L and your ASP.NET framework
        sanitized = courses.text.replace("while(1);", "")
        # At this point, the content should be valid json that we can load
        json_blob = json.loads(sanitized)

        # json_blob['Payload']['Html'] is literally rendered html that contains everything we need. But, it's HTML.
        # We're going to parse it with BS4 so we can read it.
        # Holy shit this worked
        page_soup = BeautifulSoup(json_blob['Payload']['Html'], "html.parser")

        # Now, we have a semi-nice table we can parse for all our courses. It's in the format of
        #    | Course Name  | Course Code  | Semester  | Standard Department | Start  | End
        # and all we need to do is find all the `tr`- table row
        courses = page_soup.find_all('tr')
        parsed_courses = []
        for course in courses:
            _course_soup = course.find_all('td')
            if len(_course_soup) < 5:
                logger.debug("Ignoring course row due to less than expected data length")
                continue

            metadata = {}
            # Find the name and ID. D2l puts the first column as a <th>, so we need to keep this mind
            name = course.find('th').find('a')
            metadata['name'] = name.text.strip().replace("/", "_")
            metadata['id'] = name.get('href').split('/')[-1]
            metadata['course_code'] = _course_soup[0].find('div').text.strip()
            metadata['semester'] = _course_soup[1].find('div').text.strip()
            metadata['dept'] = _course_soup[2].find('div').text.strip()
            metadata['start'] = _course_soup[3].find('div').text.strip()
            metadata['end'] = _course_soup[4].find('div').text.strip()

            parsed_courses.append(metadata)

    logger.info("I've found {} courses".format(len(parsed_courses)))

    # Now that we have a list of courses, we can iterate into each course
    # and parse, process, and download all at once
    total_files = 0
    bar = tqdm.tqdm(range(0, len(parsed_courses)), position=0)
    for i in bar:
        bar.set_description("Processing {}".format(parsed_courses[i]['course_code']))
        # Dropbox Files. We're using this URL as we're looking for 200 results at a time. I don't want to
        # implement recursive search here, so let's hope you have less than 200 assignments...
        dbx = session.get("{base}d2l/lms/dropbox/user/folders_list.d2l?ou={cid}&isprv=0&d2l_stateScopes=%7B1%3A%5B%27gridpagenum%27,%27search%27,%27pagenum%27%5D,2%3A%5B%27lcs%27%5D,3%3A%5B%27grid%27,%27pagesize%27,%27htmleditor%27,%27hpg%27%5D%7D&d2l_stateGroups=%5B%27grid%27,%27gridpagenum%27%5D&d2l_statePageId=399&d2l_state_grid=%7B%27Name%27%3A%27grid%27,%27Controls%27%3A%5B%7B%27ControlId%27%3A%7B%27ID%27%3A%27grid_main%27%7D,%27StateType%27%3A%27%27,%27Key%27%3A%27%27,%27Name%27%3A%27gridFolders%27,%27State%27%3A%7B%27PageSize%27%3A%27200%27,%27SortField%27%3A%27DropboxId%27,%27SortDir%27%3A0%7D%7D%5D%7D&d2l_state_gridpagenum=%7B%27Name%27%3A%27gridpagenum%27,%27Controls%27%3A%5B%7B%27ControlId%27%3A%7B%27ID%27%3A%27grid_main%27%7D,%27StateType%27%3A%27pagenum%27,%27Key%27%3A%27%27,%27Name%27%3A%27gridFolders%27,%27State%27%3A%7B%27PageNum%27%3A1%7D%7D%5D%7D&d2l_change=0".format(base=D2L_BASEURL, cid=parsed_courses[i]['id']))
        # TODO Request Validation
        dropbox_soup = BeautifulSoup(dbx.text, "html.parser")
        assignments_container = dropbox_soup.find('table', attrs={"id": "z_b"})

        assignments = {}
        assignment_rows = assignments_container.find_all('tr')
        if 'There are no assignments' in assignment_rows[0].text:
            break
        _current_section = ""
        for row in assignment_rows[1:]:
            if row.get('class') is not None and 'd_ggl2' in row.get('class'):
                # this is the category heading
                _current_section = row.find('span').text.strip()
                continue

            assignments[_current_section] = []
            # Fuck this shit right here
            name_container = row.find('th')
            if name_container is None:
                # fuck you. No idea why we were getting a null row here
                continue

            name_container = name_container.find('div', attrs={"class": "d2l-foldername"})
            if name_container.find('a'):
                name_container = row.find('th').find('a')
            else:
                name_container = name_container.find('label')

            tds = row.find_all('td')
            # If you want to capture score, it's index 0. Feedback is index 2
            submissions = tds[1]

            # We need to open the submissions page, and then find all the files
            # As I parse this stuff, I realize I was a really bad CSCI student. I only did like 60% of the work. heh
            submission_url = submissions.find('a').get('href') if submissions.find('a') is not None else ""
            if submission_url is "":
                logger.debug("Skipping dropbox as no submission link")
                continue

            submission_page = session.get(D2L_BASEURL + submission_url)
            submission_soup = BeautifulSoup(submission_page.text, "html.parser")

            # Find the table
            submissions = submission_soup.find('table', attrs={"id": "z_e"}).findAll('tr')[1:]
            for submission in submissions:
                link = submission.find('a').get('href')
                download(session, link, "{}/{}/dropbox/{}/{}".format(workingDirectory, parsed_courses[i]['name'], _current_section, name_container.text.strip()))
                assignments[_current_section].append([name_container.text.strip(), link])

                total_files += 1

        parsed_courses[i]['dropbox'] = assignments

        # From what I can tell, every content sections has the same "Table of Contents" section
        # We're going to use this to get all the content
        URL = "{base}d2l/le/content/{cid}/Home".format(base=D2L_BASEURL, cid=parsed_courses[i]['id'])
        contents = session.get(URL)
        # What's nice is at least it's the same across multiple endpoints
        contents_soup = BeautifulSoup(contents.text, "html.parser")

        sections = {}

        contents_container = contents_soup.find('ul', attrs={"id": "D2L_LE_Content_TreeBrowser"}).find_all('li')[1:]
        contents_bar = tqdm.tqdm(contents_container, desc="Processing Course Contents", position=1)
        for bucket in contents_bar:
            submodule_id = bucket.get("data-key").split('-')
            if len(submodule_id) != 2:
                logger.error("Unable to parse content folder")
                continue
            URL = "{base}d2l/le/content/{cid}/ModuleDetailsPartial?mId={suid}&writeHistoryEntry=1&_d2l_prc%24headingLevel=2&_d2l_prc%24scope=&_d2l_prc%24hasActiveForm=false&isXhr=true&requestId=2".format(base=D2L_BASEURL, cid=parsed_courses[i]['id'], suid=submodule_id[1])
            submodule_rq = session.get(URL)
            sanitized_contents = submodule_rq.text.replace("while(1);", "")  # We got to do this again
            submodule_payload = json.loads(sanitized_contents)
            submodule_soup = BeautifulSoup(submodule_payload['Payload']['Html'], "html.parser")
            # Find the section title
            section_title = submodule_soup.find('h1').text.strip()
            sections[section_title] = []

            section_items = submodule_soup.find_all('li')
            section_bar = tqdm.tqdm(section_items, desc="Processing {}".format(section_title), position=2)
            for section_doc in section_bar:
                links = section_doc.find_all('a', attrs={"class", "d2l-link"})
                link = None
                for _slink in links:
                    if 'viewContent' in _slink.get('href'):
                        link = _slink

                if link is None:
                    continue

                name = link.text.strip()
                href = link.get('href')

                # Dig into link to get iframe src... yes an iframe
                dl_rq = session.get("{}/{}".format(D2L_BASEURL, href))

                dl_soup = BeautifulSoup(dl_rq.text, "html.parser")
                try:
                    # Try to find PDFs
                    if dl_soup.find('div', attrs={"class": "d2l-fileviewer-pdf-native"}) is not None:
                        href = dl_soup.find('div', attrs={"class": "d2l-fileviewer-pdf-native"}).get('data-location')
                    elif dl_soup.find('div', attrs={"class": "d2l-fileviewer-pdf-pdfjs"}) is not None:
                        href = dl_soup.find('div', attrs={"class": "d2l-fileviewer-pdf-pdfjs"}).get('data-location')
                    # Try and find single Images
                    elif dl_soup.find('div', attrs={"class": "d2l-fileviewer-image"}) is not None:
                        href = dl_soup.find('div', attrs={"class": "d2l-fileviewer-image"}).get('data-location')
                    # Try and find HTML files
                    elif dl_soup.find('iframe'):
                        href = dl_soup.find('iframe').get('src')
                    # Ugh
                    elif dl_soup.find('div', attrs={"class": "d2l-fileviewer"}).find('button').text.strip() == 'Download':
                        href = "{}/{}".format(D2L_BASEURL, href).replace("viewContent", "topics/files/download").replace("View", "DirectFileTopicDownload")
                    else:
                        print("{}/{}".format(D2L_BASEURL, href))
                        href = dl_soup.find('iframe').get('src')
                except Exception:
                    logger.error("(report me) Failed to find a downloadable resource on {}/{}".format(D2L_BASEURL, href))
                    continue
                logger.debug("{} : {}", name, href)
                sections[section_title].append([name, href])
                download(session, href, "{}/{}/contents/{}".format(workingDirectory, parsed_courses[i]['name'], section_title), level=3)

                total_files += 1

            parsed_courses[i]['contents'] = sections

    logger.info("Found {} files to download", total_files)

    import pprint

    downloadables = []  # Downloadables- not deployables this time
    with tqdm.tqdm(range(0, len(parsed_courses)), desc="Creating Filesystem Paths") as bar:
        for i in bar:
            # Make Directories
            fs_path = "{}/{}".format(workingDirectory, parsed_courses[i]['name'])

            metadata = "Course: {} ({})\nDepartment: {}\nSemester: {}\nStart: {}\nEnd: {}\n".format(
                parsed_courses[i]['name'],
                parsed_courses[i]['course_code'],
                parsed_courses[i]['dept'],
                parsed_courses[i]['semester'],  # I miss quarters...
                parsed_courses[i]['start'],
                parsed_courses[i]['end']
            )

            with open("{}/metadata.txt".format(fs_path), 'w') as fh:
                fh.write(metadata)

            if 'dropbox' in parsed_courses[i]:
                for dropbox_item in parsed_courses[i]['dropbox']:
                    for item in parsed_courses[i]['dropbox'][dropbox_item]:
                        if len(item) != 2:
                            logger.debug("Skipping item in dropbox. Invalid length")
                            continue

                        dropbox_item_path = "{}/dropbox/{}".format(fs_path, item[0])
                        mkdir_recursive(dropbox_item_path)
                        downloadables.append([dropbox_item_path, item[1]])

            if 'contents' in parsed_courses[i]:
                for section in parsed_courses[i]['contents']:
                    for item in parsed_courses[i]['contents'][section]:
                        if len(item) != 2:
                            logger.debug("Skipping item in contents. Invalid length")
                            continue

                        section_path = "{}/contents/{}/{}".format(fs_path, section, item[0])
                        mkdir_recursive(section_path)
                        downloadables.append([section_path, item[1]])

    logger.info("Done.")