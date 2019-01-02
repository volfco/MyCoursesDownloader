# MyCoursesDownloader
v0.4.1

**What is it?**

MyCoursesDownloader is a python script that downloads the following from MyCourses.

* All files under "Contents"
* All submissions made to the dropbox

**Requirements**

* Python 3+ (tested on 3.6)

**Installation**

***Automagically***
I've included Nuitka complied binaries under Releases.

* **Windows** link here
* **Linux** link here
* **Mac** I don't have a Mac to make them on

***Manually***
1. Install Python
2. `pip install -r requirements.txt`
3. ???
4. Profit

**Usage**
**Arguments**

`-u RIT Username`

`-d Directory`

`--skip-review` Allows you to skip the review process prompt

`--force-review` Forces you to review each class

`--download-classes class class class...` Allows you to specify a list of classes to download. These can be partial classes such as NSSA.24, and they will be matched to NSSA.241, NSSA.245, and so on.

`--skip-classes class class class...` Allows you to specify a list of classes to skip. These can be partial classes such as NSSA.24, and they will be matched to NSSA.241, NSSA.245, and so on.
