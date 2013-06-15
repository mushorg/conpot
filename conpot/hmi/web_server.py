from gevent.wsgi import WSGIServer
import bottle
from bottle import Bottle, static_file
from jinja2 import Environment, FileSystemLoader


bottle.debug(True)
app = Bottle()
template_env = Environment(loader=FileSystemLoader("./templates"))


@app.route('/static/<filepath:path>')
def server_static(filepath):
    return static_file(filepath, root='./static')


@app.route('/favicon.ico')
def favicon():
    return None


@app.route(['/', '/<path:path>'], method=["POST", "GET"])
def root_page(path=None):
    if not path or path == "/":
        path = "index.html"
    template = template_env.get_template(path)
    return template.render()


if __name__ == '__main__':
    http_server = WSGIServer(("0.0.0.0", 80), app)
    http_server.serve_forever()