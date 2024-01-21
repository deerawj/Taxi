from sanic import Sanic, SanicException
from sanic.response import text, file
from sanic_ext import Extend
import gzip

app = Sanic(__name__)
app.config.OAS = False
app.config.TEMPLATING_PATH_TO_TEMPLATES = "templates"

Extend(app)

app.static("/", "./dist")

@app.middleware('response')
async def compress_response(request, response):
   if len(response.body) and 'gzip' in request.headers['Accept-Encoding']:
      compressed = gzip.compress(response.body)

      response.body = compressed
      response.headers["Content-Encoding"] = "gzip"
      response.headers["Vary"] = "Accept-Encoding"
      response.headers["Content-Length"] = len(compressed)

@app.middleware('request')
async def compress_request(request):
   if "Content-Encoding" in request.headers:
      if request.headers["Content-Encoding"] == "gzip":
         request.body = gzip.decompress(request.body)

@app.exception(SanicException)
async def manage_exception(request, exception):
   # exception.args = ("There is something wrong",)
   # message, = exception.args
   try:
      status_code = exception.status_code
      return text(f"Ops! There was an {status_code} Error", status=status_code)
   except:
      return text(f"Internal Server Error")

@app.get("/")
@app.ext.template("main.html")
async def index(request):
   return {"name": "World"}

@app.get("/style.css")
async def style(request):
   return await file("style.css")

if __name__ == "__main__":
   app.run(host="127.0.0.1", port=3000, dev=True)