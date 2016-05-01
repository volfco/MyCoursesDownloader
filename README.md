# MyCoursesDownloader
v0.2

**What is it?**

MyCoursesDownloader is a python script that downloads the following from MyCourses.

* All files under "Contents"
* All submissions made to the dropbox

**Requirements**

* Python 3+ (tested on 3.4)

##Usage
**Arguments**

`-u RIT Username`

`-d Directory`
###Windows
1. Install PIP requirements `C:\Python34\Scripts\pip.exe install -r .\requirements.txt`
2. Run `C:\Python34\python.exe .\mycoursesdownloader.py -u cxm7688 -d mycourses`

###Mac OS X / Linux / BSD
1. Install PIP requirements `pip install -r .\requirements.txt`
2. Run `python mycoursesdownloader.py -u cxm7688 -d mycourses`

## Todo
* Download Discussions
* Download Grades
* Download Class List
* Download Quizzes
* Get Attached Feedback for Dropbox assignments
* Handle the Edge Case in PHIL.103
* Remove Static URL so other schools can use this
* Get Ready for the summer upgrade (It has Shibboleth now [which I can already bypass])