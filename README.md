## Sat Giffer ##

Downloads and presents sentinel data in gif form! Default is to get atmospherically corrected data, which is limited to certain regions.

[Demo hosted here](http://ec2-35-159-51-103.eu-central-1.compute.amazonaws.com/). It's a micro-instance so tends to give up sometimes :X

![Should be here](https://s3.eu-central-1.amazonaws.com/sat-giffer/demo-gif.gif)

### Description ###
A Django project for making RGB satellite gifs from a slippy map box input. Inspired by [Vincent Sargo](https://twitter.com/_VincentS_)

You'll also need an AWS account + credentials for interactions with S3/The buckets hosting the satellite data.

Output looks like a time series gif like this:

![Should be here](https://s3.eu-central-1.amazonaws.com/sat-giffer/demo2.gif)

Requirements:

Python requirements included in requirements.txt

Javascript needs leaflet, leaflet-draw and underscore, all available on npm.