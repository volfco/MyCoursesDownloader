import requests
from bs4 import BeautifulSoup
import re
import os
from urllib.parse import unquote


import argparse

parser = argparse.ArgumentParser(description='Downloads all course contents from MyCourses')
parser.add_argument('-u', help='Your RIT Username that you use for MyCourses')
parser.add_argument('-p', help='Your RIT Password that you use for MyCourses')
parser.add_argument('-d', help='The directory where the files will be downloaded')

args = parser.parse_args()

if args.u is None or args.p is None or args.d is None:
    print("Invalid usage. see run.py -h")
    exit()

DIR_TO_WERK = "./" + args.d  # THIS DIRECTORY MUST EXIST

re = requests.Session()

URLS = []

# Log in
req = re.post('https://mycourses.rit.edu/d2l/lp/auth/login/login.d2l', data={
    'username': args.u,
    'password': args.p
})


def mkdir_recursive(path):
    sub_path = os.path.dirname(path)
    if not os.path.exists(sub_path):
        mkdir_recursive(sub_path)
    if not os.path.exists(path):
        os.mkdir(path)


if req.status_code is 200:
    print(" Logging into MyCourses ... M'Kay")
else:
    print("Fuck")
    exit()


# Get Current Semester Courses
# TODO!!!! MAKE SURE MYCOURSES IS SET TO THE CURRNET COUSE

r = re.get('https://mycourses.rit.edu/d2l/home')
soup = BeautifulSoup(r.text)

# but first Get the fucking D2L.LP.Web.Authentication.Xsrf.Init
xsrf = str(soup.findAll("script")[-1]).splitlines()
for line in xsrf:
    if "D2L.LP.Web.Authentication.Xsrf.Init" in line:
        xsrf = line.split("\"")[16][:-1]
        print(" Xsrf is " + xsrf)

data = {
    'widgetId': "11",
    "placeholderId$Value": "d2l_1_12_592",
    'selectedRoleId': "618",
    "_d2l_prc$headingLevel": "3",
    "_d2l_prc$scope": "",
    "_d2l_prc$hasActiveForm": "false",

    'isXhr': 'true',
    'requestId': '3',

    "d2l_referrer": xsrf,
}

# Switch to the other thing
r = re.post('https://mycourses.rit.edu/d2l/le/manageCourses/widget/myCourses/6605/ContentPartial?defaultLeftRightPixelLength=10&defaultTopBottomPixelLength=7', data=data)
r = re.get('https://mycourses.rit.edu/d2l/home')
soup = BeautifulSoup(r.text)
resp = soup.findAll(attrs={'class': 'd2l-collapsepane-content'})
for tresp in resp:
    uvA = tresp.findAll('a', attrs={'class':'d2l-left'})
    for url in uvA:
        url_code = url['href'].replace('/d2l/lp/ouHome/home.d2l?ou=', '')
        title = url['title'].split(' ')[1]
        URLS.append([url_code, title])
        print(" Found " + title)


print("\n I found {} classes\n".format(str(len(URLS))))


# -- Download that shit --
"""
Ok. let me break down this shit. MyCourses keeps the state of the page stored in its database. So, we have to make sure
we are where we want to be before we can load the page.
"""

# Loop through each course
for course in URLS:

    # Navigate to the course contents
    # We don't care what we get
    re.get("https://mycourses.rit.edu/d2l/le/content/" + course[0] + "/PartialMainView?identifier=TOC&moduleTitle=Table+of+Contents&_d2l_prc%24headingLevel=2&_d2l_prc%24scope=&_d2l_prc%24hasActiveForm=false&isXhr=true&requestId=4")

    # Now, get the page again
    toc_page = re.get("https://mycourses.rit.edu/d2l/le/content/" + course[0] + "/Home")
    toc_page_soup = BeautifulSoup(toc_page.text)
    toc_page_objs = toc_page_soup.findAll(attrs={'class': 'd2l-collapsepane'})

    # Make the class directory

    print("\n Downloading " + course[1])


    # Download "Contents"
    print("  Downloading contents")
    try:
        if not os.path.isdir(DIR_TO_WERK + "/" + course[1]):
            os.mkdir(DIR_TO_WERK + "/" + course[1])
    except FileNotFoundError:   # This error happens when there are / in the course name
        print ("  ERROR. Ah Fuck. I'll fix this in v0.0.2")
        continue

    for toc_dataset in toc_page_objs:
        pointer = toc_dataset.findAll('h2')[0].text

        tmp_links = toc_dataset.findAll(attrs={'class': 'd2l-link-main'})
        for link in tmp_links:
            file_id = link['href'].split('/')[6]
            url = "https://mycourses.rit.edu/d2l/le/content/"+ course[0] +"/topics/files/download/" + file_id  + "/DirectFileTopicDownload"
            file = re.get(url, stream=True)

            path = DIR_TO_WERK + "/" + course[1] + "/" + pointer + "/"

            if not os.path.isdir(path):
                mkdir_recursive(path)

            try:
                name = unquote(file.headers['content-disposition'].split(' ')[2].split("\"")[1])
                path += name

                print("   Downloading " + name + " to " + path)

                with open(path, 'wb') as f:
                    for chunk in file.iter_content(chunk_size=1024):
                        if chunk: # filter out keep-alive new chunks
                            f.write(chunk)
                            f.flush()
            except Exception as e:
                print("  ERROR. ", e, file_id)

    # Download "Dropbox"

    print ("  Downloading Dropbox Files")

    # There are file attachments in the dropbox
    if course[1] == "PHIL.102.15":
        print(" Edge case I do not want to deal with ")
        continue

    dropbox_resp = re.get("https://mycourses.rit.edu/d2l/lms/dropbox/user/folders_list.d2l?ou=" + course[0]  + "&isprv=0")
    dropbox_soup = BeautifulSoup(dropbox_resp.text)

    dropbox_table = dropbox_soup.find(id='z_b').findAll('tr')

    if len(dropbox_table) is 1:
        print("   No dropbox for this course")
        continue


    for dropbox_tr in dropbox_table:


        # Get the title of the thing
        if dropbox_tr.text.strip() == "":
            continue

        dropbox_item_title = dropbox_tr.findAll('th', attrs={'class': 'd_ich'})
        #print(dropbox_item_title)

        if len(dropbox_item_title) == 0:
            continue
        elif dropbox_item_title[0].find('a') is not None and len(dropbox_item_title[0].find('a')) == 1:
            dropbox_item_name = dropbox_item_title[0].find('a').text
        else:
            dropbox_item_name = dropbox_tr.find('label').text


        dropbox_item_page = dropbox_tr.findAll('a')

        WE_GUCCI = False

        for link in dropbox_item_page:
            if "folders_history.d2l" in link['href']:

                dropbox_item_page = link
                WE_GUCCI = True

        if not WE_GUCCI:
            continue


        #print("   Downloading " + dropbox_item_name)

        dropbox_dl_page = re.get("https://mycourses.rit.edu" + dropbox_item_page['href'])
        dropbox_dl_soup = BeautifulSoup(dropbox_dl_page.text)

        # Find all download links
        dropbox_dl_links = dropbox_dl_soup.findAll('span', attrs={'class': 'dfl'})

        for dropbox_dl_link in dropbox_dl_links:
            url = "https://mycourses.rit.edu" + dropbox_dl_link.find('a')['href']
            file = re.get(url, stream=True)

            path = DIR_TO_WERK + "/" + course[1] + "/dropbox/" + dropbox_item_name + "/"
            if not os.path.isdir(path):
                mkdir_recursive(path)

            try:
                name = unquote(file.headers['content-disposition'].split(' ')[2].split("\"")[1])
                path += name

                print("   Downloading " + name + " to " + path)

                with open(path, 'wb') as f:
                    for chunk in file.iter_content(chunk_size=1024):
                        if chunk: # filter out keep-alive new chunks
                            f.write(chunk)
                            f.flush()
            except Exception as e:
                print("  ERROR. ", e, " Maybe this dropbox is inaccessable?")
