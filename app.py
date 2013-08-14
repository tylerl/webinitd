import ptyexec
import re
from flask import Flask, render_template, abort, request, Response  # , url_for
from functools import wraps
import hashlib
import random
import base64

_SETTINGS={}

app=Flask(__name__,static_folder='templates/static')
def require_auth(f):
	@wraps(f)
	def decorated(*args,**kwargs):
		auth = request.authorization
		if not auth or not check_auth(auth.username,auth.password):
			return authenticate()
		return f(*args,**kwargs)
	return decorated

@app.route("/")
@require_auth
def home():
	return render_template("home.html")

@app.route("/exec/<cmd>/<op>")
@require_auth
def exec_cmd(cmd,op):
	try: 
		svc = _SETTINGS['services'][cmd]
		if not op in svc.ops:
			abort(404)
	except KeyError:
		abort(404)
	out = svc._do_exec(op)
	if request.is_xhr:
		rtn = {'ok':True, 'data': str(out)}
		if isinstance(out,Exception):
			rtn['ok']=False
		return rtn
	return render_template("exec.html", svc=svc,op=op,out=out)


@app.context_processor
def services_processor():
	return {"SERVICES":_SETTINGS['services']}

@app.template_filter('noansi')
def noansi(s):
	return _strip_ansi(s)


def authenticate():
	"Sends 401 response to authenticate"
	return Response(
		"An appropriate login is required.", 401, 
		{'WWW-Authenticate': 'Basic realm="Login Required"'}
	)


###############################################################

def check_auth(username,password):
	try: digest = _SETTINGS['logins'][username]
	except KeyError: return False
	return testhash(password,digest)

def genhash(password,iterations=10240,salt=None,algo="sha256"):
	if not salt:
		alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
		salt=""
		while len(salt) < 8:
			salt += random.choice(alphabet)
	i=0
	plain=salt+":"+password
	h = getattr(hashlib,algo)()
	while i < iterations:
		i+=1
		h.update(plain)
	return "sha256:%s:%s:%s" % (iterations, salt, base64.b64encode(h.digest()))

def testhash(password,line):
	algo,iterations,salt,digest = line.split(":")
	verification = genhash(password,int(iterations),salt,algo)
	return line == verification


class Service(object):
	def __init__(self,name,details):
		self.name=name
		for k,v in details.iteritems():
			setattr(self,k,v)

	def get_status(self):
		return self._do_exec(self.status)

	def _do_exec(self,item):
		if _SETTINGS['sudo']:
			return ptyexec.run('sudo','/etc/init.d/%s'%(self.name),item)		
		return ptyexec.run('/etc/init.d/%s'%(self.name),item)		



ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
def _strip_ansi(s):
	return ansi_escape.sub('',s)

##############################################################

def run(use_sudo,services,logins):
	_SETTINGS['sudo']=use_sudo
	_SETTINGS['services']=dict([(k,Service(k,v)) for k,v in services.iteritems()])
	_SETTINGS['logins']=logins

	import getopt,sys
	USAGE = "[-d (debug) [-host <host>] [-port <port>] [--password <auth_password>]"
	host=None
	port=None
	debug=False
	try:
		optlist, args = getopt.getopt(sys.argv[1:],"dp:h:a:",['debug','host=','port=','help','password='])
	except getopt.GetoptError as err:
		print err
		print USAGE
		sys.exit()
	for opt,val in optlist:
		if opt == '--help':
			print USAGE
			sys.exit()
		elif opt in ('-h','--host'):
			host=val
		elif opt in ('-p','--port'):
			port=int(val)
		elif opt in ('-d',):
			debug=True
		elif opt in ('--password'):
			print genhash(val)
			sys.exit()

	app.debug=debug
	if not port: port=8123
	if not host: host='0.0.0.0'
	app.run(host=host,port=port)
