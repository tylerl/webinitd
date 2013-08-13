#!/usr/bin/python

SERVICES= {
	'apache2': {
		'title': 'Web Server',
		'ops': ['stop','start','graceful'],
		'status': 'status'
	},
	'ssh': {
		'title': 'SSHd',
		'ops': ['stop','start','restart'],
		'status': 'status'
	},
}


##############################################################

import subprocess
from flask import Flask, render_template
app=Flask(__name__)

def shell_exec(*args):
	return subprocess.Popen(args, stdout=subprocess.PIPE).communicate()[0]

@app.route("/")
def home():
	return render_template("home.html")


@app.context_processor
def services_processor():
	services = dict([(k,Service(k)) for k in SERVICES.keys()])
	return {"SERVICES":services}

class Service(object):
	def __init__(self,name):
		self.name=name
		for k,v in SERVICES[name].iteritems():
			setattr(self,k,v)

	def get_status(self):
		return self._do_exec(self.status)

	def _do_exec(self,item):
		return shell_exec('/etc/init.d/%s'%(self.name),item)		


##############################################################
if __name__=="__main__":
	app.debug=True
	app.run()
	#app.run(host="0.0.0.0")
