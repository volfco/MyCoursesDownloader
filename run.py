import requests
from bs4 import BeautifulSoup
import re
import os


import pprint

DIR_TO_WERK = "./<DOWNLOAD DIRECTORY>"  # THIS DIRECTORY MUST EXIST

re = requests.Session()

URLS = []

# Log in
req = re.post('https://mycourses.rit.edu/d2l/lp/auth/login/login.d2l', data={
    'username': '<RIT USERNAME>',
    'password': '<RIT PASSWORD>'
})

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
        print(line)
        #print(line[-50:-18])
        xsrf = line.split("\"")[16][:-1]
        print(" Xsrf is " + xsrf)
        # "43":"{\"_type\":\"func\",\"N\":\"D2L.LP.Web.Authentication.Xsrf.Init\",\"P\":[\"d2l_referrer\",\"LGTVl3f1rS91eHLciWDRhpk9okic8uWr\",980578668]}",


resp = soup.findAll(attrs={'class': 'd2l-datalist'})[0].findAll('a', attrs={'class':'d2l-left'})
for url in resp:
    url_code = url['href'].replace('/d2l/lp/ouHome/home.d2l?ou=', '')
    title = url['title'].split(' ')[1]
    URLS.append([url_code, title])
    print(" Found " + title)

# Get the rest
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

    print(" \nDownloading " + course[1])

    try:
        if not os.path.isdir(DIR_TO_WERK + "/" + course[1]):
            os.mkdir(DIR_TO_WERK + "/" + course[1])
    except FileNotFoundError:   # This error happens when there are / in the course name
        print ("  ERROR. Ah Fuck. I'll fix this in v0.0.2")

    for toc_dataset in toc_page_objs:
        pointer = toc_dataset.findAll('h2')[0].text

        tmp_links = toc_dataset.findAll(attrs={'class': 'd2l-link-main'})
        for link in tmp_links:
            file_id = link['href'].split('/')[6]
            print(file_id)
            url = "https://mycourses.rit.edu/d2l/le/content/"+ course[0] +"/topics/files/download/" + file_id  + "/DirectFileTopicDownload"
            file = re.get(url, stream=True)

            path = DIR_TO_WERK + "/" + course[1] + "/" + pointer + "/"

            if not os.path.isdir(path):
                os.mkdir(path)

            try:
                name = file.headers['content-disposition'].split(' ')[2].split("\"")[1]
                path += name

                print("  Downloading " + name + " to " + path)

                with open(path, 'wb') as f:
                    for chunk in file.iter_content(chunk_size=1024):
                        if chunk: # filter out keep-alive new chunks
                            f.write(chunk)
                            f.flush()
            except Exception as e:
                print("  ERROR. ", e, file_id)

