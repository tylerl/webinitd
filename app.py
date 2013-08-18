import re
import os
import hmac
import base64
import random
import hashlib
import ptyexec
from operator import xor
from struct import Struct
from functools import wraps
from itertools import izip, starmap
from flask import Flask, render_template, abort, request, Response  # , url_for

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

@app.route("/favicon.ico")
def favicon():
	return Response(TERM_ICO,200,content_type='image/ico')
	

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

def genhash(password,iterations=1024,salt=None,algo="sha256",keylen=32):
	if not salt:
		alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
		salt=""
		while len(salt) < 8:
			salt += random.choice(alphabet)
	hashfunc = getattr(hashlib,algo)
	hashed = pbkdf2(password,salt,iterations,keylen,hashfunc)

	return "sha256:%s:%s:%s" % (iterations, salt, base64.b64encode(hashed))

def pbkdf2(data, salt, iterations, keylen, hashfunc=None):
	"""Returns a binary digest for the PBKDF2 hash algorithm of `data`
	with the given `salt`.  It iterates `iterations` time and produces a
	key of `keylen` bytes.
	* Implementation shamelessly stolen from: 
	  https://github.com/mitsuhiko/python-pbkdf2/
	"""
	_pack_int = Struct('>I').pack
	mac = hmac.new(data, None, hashfunc)
	def _pseudorandom(x, mac=mac):
		h = mac.copy()
		h.update(x)
		return map(ord, h.digest())
	buf = []
	for block in xrange(1, -(-keylen // mac.digest_size) + 1):
		rv = u = _pseudorandom(salt + _pack_int(block))
		for i in xrange(iterations - 1):
			u = _pseudorandom(''.join(map(chr, u)))
			rv = starmap(xor, izip(rv, u))
		buf.extend(rv)
	return ''.join(map(chr, buf))[:keylen]


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
		secure_fds()  # prevent FDs from leaking to child proc
		if _SETTINGS['sudo']:
			return ptyexec.run('/usr/bin/sudo','/etc/init.d/%s'%(self.name),item)		
		return ptyexec.run('/etc/init.d/%s'%(self.name),item)		

ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
def _strip_ansi(s):
	return ansi_escape.sub('',s)

FDS_SECURED=False
def secure_fds():
	global FDS_SECURED
	if FDS_SECURED: return  # only need to do this once
	for item in os.listdir("/proc/self/fd/"):
		try: ptyexec.set_close_exec(int(item))
		except: pass  # give it the ol' college-try
	FDS_SECURED=True

##############################################################

def run(use_sudo,services,logins):
	_SETTINGS['sudo']=use_sudo
	_SETTINGS['services']=dict([(k,Service(k,v)) for k,v in services.iteritems()])
	_SETTINGS['logins']=logins

	import getopt,sys
	USAGE = """Options:
	-?  --help        This message
	-d                debug mode (show exception trace in web page)
	-h <host>         listen host 
	-p <port>         listen port
	-c <cert file>    ssl certificate file
	-k <key file>     ssl key file (if different)
	-P <file>         PID file
	-l <log>          log file
	-D                daemon mode (fork and setsid)

	-- or --

	--password <auth_password>      generate and display an auth password hash (then exit)
 """
	
	host=None
	port=None
	cert=None
	key=None
	debug=False
	pidfile=None
	logfile=None
	daemon=False
	try:
		optlist, args = getopt.getopt(sys.argv[1:],"?Ddp:h:a:c:k:P:l:",
			['debug','host=','port=','help','password=','cert=','key=','pid=','log=','daemon'])
	except getopt.GetoptError as err:
		print err
		print USAGE
		sys.exit()
	for opt,val in optlist:
		if opt in ('-?' '--help'):
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
		elif opt in ('-c','--cert'):
			cert=val
		elif opt in ('-k','--key'):
			key=val
		elif opt in ('-P','--pid'):
			pidfile=val
		elif opt in ('-l','--log'):
			logfile=val
		elif opt in ('-D','--daemon'):
			daemon=True

	if cert and not key: key=cert
	if key and not cert: cert=key
	app.debug=debug
	if not port: port=8123
	if not host: host='0.0.0.0'
	run_args={'host':host,'port':port,'use_reloader':False}
	if cert:
		from OpenSSL import SSL
		context=SSL.Context(SSL.SSLv23_METHOD)
		context.use_privatekey_file(key)
		context.use_certificate_file(cert)
		run_args['ssl_context']=context

	if logfile:
		lfn = os.open(logfile,os.O_WRONLY | os.O_APPEND | os.O_CREAT,0644)
		os.dup2(lfn,1)
		os.dup2(lfn,2)
		ptyexec.set_close_exec(lfn)

	if pidfile: # open before fork so we know we have perms
		pidfile=open(pidfile,"w")

	# get all the errors out of the way before we go daemon mode	
	if daemon:
		pid = os.fork()
		if pid:
			sys.exit(0)  # Our work here is done
		os.setsid()
		os.close(0)
		if not logfile:
			os.close(1)
			os.close(2)

	if pidfile:
		pidfile.write("%i" % (os.getpid(),)) # write NEW pid
		pidfile.close()

	app.run(**run_args)

# it's be a shame to waste a whole file on this
TERM_ICO=base64.b64decode("""
AAABAAEAEBAAAAAAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAQAQAAAAAAAAAAAAAAAAA
AAAAAAD///8B////Af///wH///8B////Af///wH///8B////Af///wH///8B////Af///wH///8B
////Af///wH///8Bw5Ftm8OOaP/Ai2b/vohk/7uFYf+5g1//toBe/7R+XP+yfFr/sXtY/655V/+t
dlb/q3VU/6lzU/+pcVH/o3BRm8iSbP9SUlL/U1NT/1RUVP9VVVX/VlZW/1dXV/9XV1f/WFhY/1lZ
Wf9aWlr/W1tb/1xcXP9cXFz/XV1d/6lyUf/KlG7/Tk5O/z09Pf89PT3/Pj4+/z8/P/9BQUH/QkJC
/0NDQ/9ERET/RUVF/0ZGRv9GRkb/SEhI/1paWv+qc1P/zJdv/0tLS/84ODj/OTk5/zo6Ov88PDz/
PT09/z8/P/8/Pz//QUFB/0JCQv9CQkL/RERE/0VFRf9XV1f/rHVU/8+acv9HR0f/MzMz/zQ0NP82
Njb/Nzc3/zk5Of86Ojr/Ozs7/zw8PP8+Pj7/Pz8//0BAQP9BQUH/VVVV/614Vv/RnHP/QkJC/y8v
L/8wMDD/MTEx/zMzM/80NDT/NjY2/zY2Nv84ODj/Ojo6/zs7O/89PT3/PT09/1JSUv+welj/1J51
/z09Pf8pKSn/0dHR/62trf8uLi7/Ly8v/zExMf8yMjL/NDQ0/zY2Nv83Nzf/ODg4/zo6Ov9OTk7/
snxa/9Wgdv85OTn/JSUl/yYmJv/e3t7/dHR0/yoqKv8sLCz/LS0t/y8vL/8xMTH/MjIy/zQ0NP81
NTX/S0tL/7V+XP/Yonn/NDQ0/yAgIP/Pz8//qKio/yQkJP8lJSX/JiYm/ygoKP8qKir/LCws/y0t
Lf8vLy//MTEx/0ZGRv+3gV7/2aN5/zQ0NP8gICD/ISEh/yIiIv8kJCT/JSUl/yYmJv8oKCj/Kioq
/ywsLP8tLS3/Ly8v/zExMf9GRkb/uoVg/9ukev8xMTH/MjIy/zMzM/80NDT/NTU1/zY2Nv83Nzf/
OTk5/zs7O/88PDz/PT09/z8/P/9BQUH/Q0ND/72HY//cp3v/26R6/9qjef/Yonn/16F4/9Wfdv/T
nnT/0Zxz/8+acv/Nl3D/y5Vu/8mUbP/HkWv/xI9p/8ONZ//Ai2b/3ayF/fHczv/qwaD/6LmS/+i5
kv/ouZL/6LmS/+i5kv/ouZL/zcjF/+i5kv/NyMX/6LmS/0Rk///oxKf/wZBv/d2shsPdsY313Kd7
/9ymev/apHr/2KJ5/9ihef/VoHb/1J51/9Kdc//PmnL/zplw/8uWb//JlGz/xJp69cOTccP///8B
////Af///wH///8B////Af///wH///8B////Af///wH///8B////Af///wH///8B////Af///wH/
//8BAAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA
//8AAP//AAD//w==""")
