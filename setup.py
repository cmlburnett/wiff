from setuptools import setup

majv = 1
minv = 0

setup(
	name = 'wiff',
	version = "%d.%d" %(majv,minv),
	description = "Waveform Interchange File Format",
	author = "Colin ML Burnett",
	author_email = "cmlburnett@gmail.com",
	url = "",
	packages = ['wiff'],
	package_data = {'wiff': ['wiff/__init__.py']},
	classifiers = [
		'Programming Language :: Python :: 3.7'
	],
	test_suite = "tests",
)
