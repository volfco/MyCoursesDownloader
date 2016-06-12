# MyCoursesDownloader
v0.3.0

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

`--skip-review` Allows you to skip the review process prompt

`--force-review` Forces you to review each class

`--download-classes class class class...` Allows you to specify a list of classes to download. These can be partial classes such as NSSA.24, and they will be matched to NSSA.241, NSSA.245, and so on.

`--skip-classes class class class...` Allows you to specify a list of classes to skip. These can be partial classes such as NSSA.24, and they will be matched to NSSA.241, NSSA.245, and so on.


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
* Download Announcements
* Refactor Each subsection of MyCourses into its own module
* Handle the Edge Case in PHIL.103
* Remove Static URL so other schools can use this