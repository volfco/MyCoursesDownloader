"""
The MIT License (MIT)

Copyright (c) 2015 Colum McGaley <cxm7688@rit.edu>

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

import requests
from bs4 import BeautifulSoup
import re
import os
from urllib.parse import unquote
import argparse
import sys
import getpass
import json
import datetime

# basically, mkdir -p /blah/blah/blah
def mkdir_recursive(path):
    sub_path = os.path.dirname(path)
    if not os.path.exists(sub_path):
        mkdir_recursive(sub_path)
    if not os.path.exists(path):
        os.mkdir(path)

def safeFilePath(path):
    ## Fucking unicode
    path = ''.join([i if ord(i) < 128 else ' ' for i in path])

    bad = ["<", ">", ":", "|", "?", "*", " / ", " \ "]
    for char in bad:
        path = path.replace(char, " ")
    return path


def output(level="Info", message=""):
    print("[{0}][{1:>8}]  {2}".format(str(datetime.datetime.now()), level, message))

if __name__ == "__main__":

    if sys.version_info[0] < 3:
        print("I need python 3+")
        exit()

    parser = argparse.ArgumentParser(description='Downloads all course contents from MyCourses')
    parser.add_argument('-u', help='Your RIT Username that you use for MyCourses')
    parser.add_argument('-d', help='The directory where the files will be downloaded')

    args = parser.parse_args()

    if args.u is None or args.d is None:
        output(level="Warning", message="Invalid usage. see mycoursesdownloader.py -h")
        exit()

    password = getpass.getpass("Enter your RIT password: ")

    workingDirectory = "./" + args.d

    if not os.path.exists(workingDirectory):
        output(level="Warning", message="Directory does not exist. Creating")
        mkdir_recursive(workingDirectory)

    URLS = []   # [("22222", "PLOS.140"), ("11111", "NSSA.220")]

    # Start our session.
    re = requests.Session()
    # Log in
    req = re.post('https://mycourses.rit.edu/d2l/lp/auth/login/login.d2l', data={
        'username': args.u,
        'password': password
    })

    if "Invalid Username" in req.text:
        output(level="Error", message="MyCourses rejected your username and/or password")
        exit()
    else:
        output(level="Info", message="Good Login")

    r = re.get('https://mycourses.rit.edu/d2l/home')
    soup = BeautifulSoup(r.text, "html.parser")

    xsrf = str(soup.findAll("script")[-1]).splitlines()
    for line in xsrf:
        if "D2L.LP.Web.Authentication.Xsrf.Init" in line:
            xsrf = line.split("\"")[16][:-1]
            output(level="Debug", message="Xsrf is " + xsrf)

    # Switch to the current courses.
    data = {
        'widgetId': "11",
        "_d2l_prc$childScopeCounters": "filtersData:0",
        "_d2l_prc$headingLevel": "3",
        "_d2l_prc$scope": "",
        "_d2l_prc$hasActiveForm": "false",
        'isXhr': 'true',
        'requestId': '3',
        "d2l_referrer": xsrf,
    }
    r = re.post('https://mycourses.rit.edu/d2l/le/manageCourses/widget/myCourses/6605/ContentPartial?defaultLeftRightPixelLength=10&defaultTopBottomPixelLength=7', data=data)
    # d2l changed to ajax. woo!
    soup = BeautifulSoup(json.loads(r.text.replace("while(1);", ""))['Payload']['Html'], "html.parser")
    resp = soup.findAll(attrs={'class': 'd2l-collapsepane-content'})
    uvA = resp[0].findAll('a', attrs={'class':'d2l-left'})
    for url in uvA:
        url_code = url['href'].replace('/d2l/lp/ouHome/home.d2l?ou=', '')
        title = url['title'].split(' ')[1]
        URLS.append((url_code, title))

    # Now, switch to the other section that lists all the old courses.
    data = {
        'widgetId': "11",
        "placeholderId$Value": "d2l_1_12_592",
        'selectedRoleId': "618",    # This will proably change in the future
        "_d2l_prc$headingLevel": "3",
        "_d2l_prc$scope": "",
        "_d2l_prc$hasActiveForm": "false",
        'isXhr': 'true',
        'requestId': '3',
        "d2l_referrer": xsrf,
    }
    r = re.post('https://mycourses.rit.edu/d2l/le/manageCourses/widget/myCourses/6605/ContentPartial?defaultLeftRightPixelLength=10&defaultTopBottomPixelLength=7', data=data)
    r = re.get('https://mycourses.rit.edu/d2l/home')
    soup = BeautifulSoup(r.text, "html.parser")
    resp = soup.findAll(attrs={'class': 'd2l-collapsepane-content'})
    for tresp in resp:
        uvA = tresp.findAll('a', attrs={'class':'d2l-left'})
        for url in uvA:
            url_code = url['href'].replace('/d2l/lp/ouHome/home.d2l?ou=', '')
            title = url['title'].split(' ')[1]
            URLS.append((url_code, title))

    # Check for duplicate entries.
    URLS = set(tuple(element) for element in URLS)

    # List the classes
    for rit_class in URLS:
        output(level="Info", message=("Found " + rit_class[1]))
    print("\nI found {} classes.".format(str(len(URLS))))
    print("Would you like to review them?")
    print("Press r followed by enter to review or just press enter...")

    user_response = input("? ")

    # copy URLS
    TURLS = []

    if user_response == "r":
        print("\nPress d followed by enter to skip class. Press enter to accept.\n")
        for rit_class in URLS:
            resp = input(rit_class[1] + " ? ")
            if resp != "d":
                TURLS.append(rit_class)
        output(level="Info", message=("Deleted " + str(len(URLS) - len(TURLS))))
        URLS = []
        URLS = TURLS
    else:
        pass

    # Loop through each course
    TOTAL_BYTES = 0;
    for course in URLS:
        re.get("https://mycourses.rit.edu/d2l/le/content/" + course[0] + "/PartialMainView?identifier=TOC&moduleTitle=Table+of+Contents&_d2l_prc%24headingLevel=2&_d2l_prc%24scope=&_d2l_prc%24hasActiveForm=false&isXhr=true&requestId=4")

        toc_page = re.get("https://mycourses.rit.edu/d2l/le/content/" + course[0] + "/Home")
        toc_page_soup = BeautifulSoup(toc_page.text, "html.parser")
        toc_page_objs = toc_page_soup.findAll(attrs={'class': 'd2l-collapsepane'})

        # Make the class directory

        output(level="Info", message="Processing " + course[1])
        path = workingDirectory + "/" + course[1].replace("/", ".")    # course[1] is the course code, like NSSA.220

        if not os.path.isdir(safeFilePath(path)):
            output(level="Info", message="Directory does not exist.")
            output(level="Debug", message=safeFilePath(path))
            mkdir_recursive(safeFilePath(path))

        for toc_dataset in toc_page_objs:
            # This is what the folder will be called. I'm replacing the / with a space so we dont get
            pointer = toc_dataset.findAll('h2')[0].text.replace("/", ".")

            tmp_links = toc_dataset.findAll(attrs={'class': 'd2l-link-main'})
            for link in tmp_links:
                file_id = link['href'].split('/')[6]
                url = "https://mycourses.rit.edu/d2l/le/content/"+ course[0] +"/topics/files/download/" + file_id  + "/DirectFileTopicDownload"
                file = re.get(url, stream=True)

                if file.status_code == 302:  # D2L, you don't fucking redirect a 404/403 error.
                    output(level="Error", message="Requested file is 404")

                path = workingDirectory + "/" + course[1] + "/" + pointer + "/"

                if not os.path.isdir(safeFilePath(path)):
                    output(level="Info", message="Directory does not exist.")
                    output(level="Debug", message=safeFilePath(path))
                    mkdir_recursive(safeFilePath(path))
                try:
                    name = unquote(file.headers['content-disposition'].split(' ')[2].split("\"")[1])
                    path += name

                    output(level="Progress", message="Downloading " + safeFilePath(name))

                    with open(safeFilePath(path), 'wb') as f:
                        for chunk in file.iter_content(chunk_size=1024):
                            if chunk:  # filter out keep-alive new chunks
                                f.write(chunk)
                                f.flush()
                                TOTAL_BYTES += 1024
                except Exception as e:
                    output(level="Error", message="Error: {}. File ID: {}".format(e, file_id))
                    output(level="Debug", message="Path " + url)

        # Download "Dropbox"
        if course[1] == "PHIL.102.15":
            print(" Edge case I do not want to deal with ")
            continue

        dropbox_resp = re.get("https://mycourses.rit.edu/d2l/lms/dropbox/user/folders_list.d2l?ou=" + course[0]  + "&isprv=0")
        dropbox_soup = BeautifulSoup(dropbox_resp.text)

        try:
            dropbox_table = dropbox_soup.find(id='z_b').findAll('tr')
        except AttributeError:
            dropbox_table = []

        if len(dropbox_table) is 1 or len(dropbox_table) is 0:
            output(level="Info", message="No dropbox for {}".format(course[1]))
            continue


        for dropbox_tr in dropbox_table:
            # Get the title of the thing
            if dropbox_tr.text.strip() == "":
                continue

            dropbox_item_title = dropbox_tr.findAll('th', attrs={'class': 'd_ich'})

            if len(dropbox_item_title) == 0:
                continue
            elif dropbox_item_title[0].find('a') is not None and len(dropbox_item_title[0].find('a')) == 1:
                dropbox_item_name = dropbox_item_title[0].find('a').text.replace("/", ".")
            else:
                dropbox_item_name = dropbox_tr.find('label').text.replace("/", ".")


            dropbox_item_page = dropbox_tr.findAll('a')

            WE_GUCCI = False
            for link in dropbox_item_page:
                if "folders_history.d2l" in link['href']:

                    dropbox_item_page = link
                    WE_GUCCI = True

            if not WE_GUCCI:
                continue

            output(level="Info", message="Processing Dropbox for" + safeFilePath(dropbox_item_name))
            dropbox_dl_page = re.get("https://mycourses.rit.edu" + dropbox_item_page['href'])
            dropbox_dl_soup = BeautifulSoup(dropbox_dl_page.text)

            # Find all download links
            dropbox_dl_links = dropbox_dl_soup.findAll('span', attrs={'class': 'dfl'})

            for dropbox_dl_link in dropbox_dl_links:
                url = "https://mycourses.rit.edu" + dropbox_dl_link.find('a')['href']
                file = re.get(url, stream=True)

                if file.status_code == 302:
                    output(level="Error", message="Requested file is 404")

                path = workingDirectory + "/" + course[1] + "/dropbox/" + dropbox_item_name + "/"
                if not os.path.isdir(safeFilePath(path)):
                    mkdir_recursive(safeFilePath(path))

                try:
                    name = unquote(file.headers['content-disposition'].split(' ')[2].split("\"")[1])
                    path += name

                    output(level="Progress", message="Downloading " + safeFilePath(name))

                    with open(safeFilePath(path), 'wb') as f:
                        for chunk in file.iter_content(chunk_size=1024):
                            if chunk:  # filter out keep-alive new chunks
                                f.write(chunk)
                                f.flush()
                                TOTAL_BYTES += 1024
                except Exception as e:
                    output(level="Error", message="Error: {}. File ID: {}".format(e, file_id))
                    output(level="Debug", message="Path " + url)

    print(TOTAL_BYTES / 1024 / 1024)  # KB / MB

    print("End Of Line.")