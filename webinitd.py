#!/usr/bin/python
USE_SUDO=True
SERVICES= {
	'apache2': {
		'title': 'Apache Web Server',
		'ops': ['status', 'stop','start','graceful'],
		'status': 'status'
	},
	'ssh': {
		'title': 'SSH Server',
		'ops': ['status','stop','start','restart'],
		'status': 'status'
	},
}

LOGINS = {
	'admin': 'sha256:10240:FcbYJZ4Z:ZDHbf8Gx/GDXVD3W33xjqnEuf3TWv41rGrSig8fM7d4=',
}

if __name__=="__main__":
	import app
	app.run(USE_SUDO,SERVICES,LOGINS)
