import json
import ssl
import asyncio
from aiohttp import web
import os
import y1

async def handle(request: web.Request) -> web.Response:
	"""A simple handler that greets the user."""
	name = request.match_info.get('name', "Anonymous")
	text = f"Hello, {name}, from your secure aiohttp server!"
	return web.Response(text=text)

async def handle_file(request):
	data = await request.post()
	uploaded_file = data['file']  # 'file' is the name attribute in your HTML form
	filename = uploaded_file.filename
	content = uploaded_file.file.read()  # Read file content as bytes

	# Save the file locally
	with open(f'{filename}', 'wb') as f:
		f.write(content)

	return web.Response(text=f"Uploaded {filename} successfully!")
	
async def handle_params(request: web.Request) -> web.StreamResponse:
	"""
	Handles a POST request, runs a potentially long-running computation,
	and streams the results back to the client as a JSON array.
	"""
	try:
		# 1. Prepare the streaming response object.
		# This allows us to send headers first, then data chunks later.
		response = web.StreamResponse(
			status=200,
			reason='OK',
			headers={'Content-Type': 'application/json', 'X-Content-Type-Options': 'nosniff'},
		)
		await response.prepare(request)

		# 2. Get initial parameters from the POST request.
		#data = await request.post()
		data = await request.json()
		bin_data = bytes.fromhex(data['bin'])
		no = int(data['no'], 16)
		mask = int(data['mask'], 16)
		#print(f"Initial params: {bin_data.hex()[:8]} {no=:08x} {mask=:08x}")
	

		# 3. Start streaming the response. We'll send a JSON array.
		#await response.write(b'[')
		#first_item = True
		loop = asyncio.get_running_loop()

		# This loop simulates a process that generates multiple results over time.
		for i in range(5):  # Stream 5 results for demonstration
			# The y1.foo2 function is a blocking C extension. To avoid freezing
			# the server, we run it in a separate thread using an executor.
			#print(f"Iteration {i}: {bin_data.hex()[:8]} {no=:08x} {mask=:08x}")
			new_bin, new_no, new_mask, ret = await loop.run_in_executor(
				None, y1.foo2, bin_data, no, mask
			)
			#if not first_item:
			#	await response.write(b',')

			if ret != -1:
				print(f"Iteration {i}: {new_no=:08x} {new_mask=:08x} {ret=}")
				json_data = {"result": "True", "bin": new_bin.hex(), "no": f"{new_no:08x}", "mask": f"{new_mask:08x}"}
			else:
				print(f"Iteration {i}: {new_no=:08x} Computation failed. {ret=}")
				json_data = {"result": "False"}
			no = new_no+1
			mask = mask

			await response.write(json.dumps(json_data).encode('utf-8')+b'\r\n')
			first_item = False
			await asyncio.sleep(.1)  # Pause to make streaming visible

			
		# 4. Close the JSON array and signal the end of the stream.
		#await response.write(b']')
		await response.write_eof()

	except ConnectionResetError:
		print("Client disconnected during streaming.")

	return response

# --- Main Application Setup ---
app = web.Application()
app.add_routes([
	web.get('/', handle),
	web.post('/file', handle_file),
	web.post('/params', handle_params),
])

def main():
	"""Sets up the SSL context and runs the aiohttp application."""
	
	cert_file = 'cert.pem'
	key_file = 'key.pem'

	# --- SSL Context Setup ---
	# For a robust and secure server, it's recommended to use
	# ssl.create_default_context.
	# ssl.Purpose.CLIENT_AUTH means the context is for a server-side socket,
	# which will authenticate clients.
	ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
	ssl_context.check_hostname = False
	ssl_context.verify_mode = ssl.CERT_NONE
	# Load your server's certificate and private key.
	# In a production environment, you would use a certificate from a
	# trusted Certificate Authority (CA) like Let's Encrypt.
	try:
		ssl_context.load_cert_chain(certfile=cert_file, keyfile=key_file)
		print(f"Successfully loaded certificate from '{cert_file}' and key from '{key_file}'.")
	except FileNotFoundError:
		print("=" * 60)
		print(f"ERROR: Could not find '{cert_file}' or '{key_file}'.")
		print("You can generate a self-signed certificate for development with:")
		print('openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes -subj "/CN=localhost"')
		print("=" * 60)
		return
	except ssl.SSLError as e:
		print(f"An SSL error occurred: {e}")
		print("Please ensure your certificate and key files are valid and match.")
		return

	

	# --- Run the application with HTTPS ---
	# Passing the `ssl_context` to `run_app` is what enables HTTPS.
	host = '0.0.0.0'
	port = 8001
	print(f"Starting secure server on https://{host}:{port}")
	web.run_app(app, host=host, port=port, ssl_context=ssl_context)
	#web.run_app(app, host=host, port=port)


if __name__ == '__main__':
	script_dir = os.path.dirname(os.path.abspath(__file__))
	os.chdir(script_dir)
	main()
