Pet project in Django for making RGB satellite gifs from a slippy map box input. Inspired by [Vincent Sargo](https://twitter.com/_VincentS_)

You'll need to update the paths in sat_giffer/settings to get it to run locally. You'll also need an AWS account + credentials for interactions with S3/The buckets hosting the satellite data.

An example of the application running is hosted [here](http://ec2-35-159-51-103.eu-central-1.compute.amazonaws.com/). It's a micro-instance so tends to give up sometimes :X

Output looks like a time series gif like this:

![Should be here](https://s3.eu-central-1.amazonaws.com/sat-giffer/gifs/53.38238175058855,-6.479959599832915,53.40245549675814,-6.4435737054752105.gif)

Requirements:

Python requirements included in requirements.txt

Javascript needs leaflet, leaflet-draw and underscore, all available on npm