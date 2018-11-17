## Sat Giffer ##

Downloads and presents sentinel data in gif form!

![Should be here](https://im5.ezgif.com/tmp/ezgif-5-493a7feb4cc8.gif)

Pet project in Django for making RGB satellite gifs from a slippy map box input. Inspired by [Vincent Sargo](https://twitter.com/_VincentS_)

You'll need to update the paths in sat_giffer/settings to get it to run locally. You'll also need an AWS account + credentials for interactions with S3/The buckets hosting the satellite data.

An example of the application running is hosted [here](http://ec2-35-159-51-103.eu-central-1.compute.amazonaws.com/). It's a micro-instance so tends to give up sometimes :X

Output looks like a time series gif like this:

![Should be here](https://media.giphy.com/media/2gYhRXt8ikmAO7FX2Z/giphy.gif)

Requirements:

Python requirements included in requirements.txt

Javascript needs leaflet, leaflet-draw and underscore, all available on npm