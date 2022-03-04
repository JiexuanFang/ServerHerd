"""
Note that this piece of code is (of course) only a hint
you are not required to use it
neither do you have to use any of the methods mentioned here
The code comes from
https://asyncio.readthedocs.io/en/latest/tcp_echo.html
To run:
1. start the echo_server.py first in a terminal
2. start the echo_client.py in another terminal
3. follow print-back instructions on client side until you quit
"""

import asyncio
import argparse
import sys
import re
import logging
import time
import aiohttp
import json
# ports: 10640 - 10647
# servernames:  'Juzang', 'Bernard', 'Jaquez', 'Campbell', 'Clark'

KEY = "AIzaSyB1wMHSPxW5XC33FXuEaqCJDWdVYXCVRvY"
ports = {'Juzang':10640, 'Bernard':10641, 'Jaquez':10642,
    'Campbell':10643, 'Clark':10644}
talks = {
    'Juzang':['Campbell', 'Clark', 'Bernard'],
    'Bernard':['Juzang', 'Jaquez', 'Campbell'],
    'Clark':['Jaquez', 'Juzang'],
    'Jaquez':['Bernard', 'Clark'],
    'Campbell':['Juzang','Bernard']
}

class Server:
    def __init__(self, name, ip='127.0.0.1', message_max_length=1e6):    
        self.name = name
        logging.basicConfig(filename=f'{name}.log', level=logging.DEBUG)
        self.ip = ip
        try:
            self.port = ports[name]
        except KeyError:
            logging.error("invalid server name. aborting server setup")
            sys.exit(1)
        self.message_max_length = int(message_max_length)
        self.locations = {}
        


    def update_location(self, user, at):
        logging.info(f"updating location")
        if user in self.locations: 
            logging.info(f"updating user {user} location")
        else:
            logging.info(f"adding new user {user} location")
        self.locations[user] = at

    def terminate(self):
        logging.info("closing server")
        logging.info("user locations recorded:")
        logging.info(self.locations)
    
    #checks if input string is of ISO format
    def check_ISO(self, str):
        ISO_check = re.match("[\+-]?[0-9]+(\.[0-9]+)?[\+-]?[0-9]+(\.[0-9]+)?", str)
        is_ISO = bool(ISO_check)
        return is_ISO

    async def handle_IAMAT(self, message):
        # check if the request format is valid
        logging.info("IAMAT request recieved")
        args = message.split()
        if(len(args) != 4):
            logging.info("invalid IAMAT request format")
            return f'? {message}'
        if(not self.check_ISO(args[2])):
            logging.info("invalid ISO in IAMAT request")
            return f'? {message}'
        logging.info("valid IAMAT format")

        # calculate the time difference
        time_difference = time.time() - float(args[3])
        if time_difference >= 0:
            time_difference = f"+{time_difference}"
        else:
            time_difference = f"-{time_difference}"

        #prepare the response
        logging.info("generating response")
        response = f"AT {self.name} {time_difference} {args[1]} {args[2]} {args[3]}"
        self.update_location(args[1], response)
        await self.flood(response)
        return response

    async def handle_WHATSAT(self, message):
        #check request format
        logging.info("WHATSAT request recieved")
        args = message.split()
        radius= args[2]
        bound = args[3]
        if(len(args) != 4 or self.not_number(radius) or self.not_number(bound)):
            logging.error("invalid WHATSAT request")
            return f'? {message}'
        radius = int(radius)
        bound = int(bound)
        if(radius > 50 or radius < 0 or bound > 20 or bound < 0):
            logging.error("invalid WHATSAT parameters")
            return f'? {message}'
        logging.info("valid WHATSAT format")
        
        user_msg = self.locations[args[1]]
        logging.info(f"user message is {user_msg}")
        location = user_msg.split()[4]
        logging.info(f"user location is {location}")
        places = await self.nearby_search(location, radius, bound)
        response = f"{user_msg}\n{places}\n\n"
        #response = f"WHATSAT: {message}"
        return response

    async def nearby_search(self, location, radius, upper_bound):
        logging.info(f"location: {location}")
        coords = ','.join(re.findall('[-]?[^+-]+', location))
        logging.info(f"coords: {coords}")
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = [("key", KEY), ("location", coords), ("radius", radius)]
        logging.info(f"Querying location {coords}")

        #querying to the google places API
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                logging.debug(str(resp.url))
                txt = await resp.text()
        places = json.loads(txt)
        results = places['results']
        logging.info(f"Retrieved {len(results)} places")
        places["results"] = results[0:upper_bound]
        return json.dumps(places).rstrip('\n')

    async def handle_AT(self, message):
        #check request format
        logging.info("AT request recieved")
        args = message.split()
        user = args[3]
        message_time = args[5]
        if(len(args) != 6):
            logging.error("invalid AT request")
            return f'? {message}'
        if(not self.check_ISO(args[4])):
            logging.error("invalid ISO in AT request")
            return f'? {message}'
        logging.info("valid AT format")

        if user not in self.locations: 
            logging.info(f"updating user {user} location")
            self.update_location(args[3], message)
            await self.flood(message)
            return message
        if (float(message_time) > float(self.locations[user].split()[5])):
            logging.info(f"updating user {user} location")
            self.locations[user] = message
            await self.flood(message)
            return message
        else:
            logging.info("message already receiveed")

        return ""

    #flooding algorithm
    async def flood(self, message):
        for server_name in talks[self.name]: 
            # get the reader and writer for the corresponding server
            try:
                reader, writer = reader, writer = await asyncio.open_connection('127.0.0.1', ports[server_name])
            except:
                logging.error(f"Couldn't connect to server {server_name}")
                continue

            #pass the message to the server
            logging.info(f"Propagating message from {self.name} to {server_name}: {message}")
            writer.write(message.encode())
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            logging.info(f"Progagation success, message sent")


    async def handle_echo(self, reader, writer):
        """
        on server side
        """
        #flag to check whether to involke the writer
        WRITE = True

        data = await reader.read(self.message_max_length)
        message = data.decode()
        addr = writer.get_extra_info('peername')
        logging.info("{} received {} from {}".format(self.name, message, addr))
        #print("{} received {} from {}".format(self.name, message, addr))
        parsed_message = message.split()
        sendback_message = f"? {message}"

        #process the requests

        if parsed_message[0] == 'IAMAT':
            sendback_message = await self.handle_IAMAT(message)
        elif parsed_message[0] == 'AT':
            sendback_message = await self.handle_AT(message)
            WRITE = False
        elif parsed_message[0] == 'WHATSAT':
            sendback_message = await self.handle_WHATSAT(message)

        
        if WRITE:
            #print("{} send: {}".format(self.name, sendback_message))
            logging.info("{} send: {}".format(self.name, sendback_message))
            writer.write(sendback_message.encode())
            await writer.drain()

        #print("close the client socket")
        writer.close()

    async def run_forever(self):
        server = await asyncio.start_server(self.handle_echo, self.ip, self.port)

        # Serve requests until Ctrl+C is pressed
        logging.info(f'serving on {server.sockets[0].getsockname()}')
        #print(f'serving on {server.sockets[0].getsockname()}')
        async with server:
            await server.serve_forever()
        # Close the server
        server.close()

    def not_number(self, x):
        try:
            float(x)
        except:
            return True
        return False
        

def main():
    parser = argparse.ArgumentParser('CS131 project example argument parser')
    parser.add_argument('server_name', type=str,
                        help='required server name input')
    args = parser.parse_args()

    #print("Hello, welcome to server {}".format(args.server_name))

    server = Server(args.server_name)
    try:
        asyncio.run(server.run_forever())
    except KeyboardInterrupt:
        server.terminate()
        pass


if __name__ == '__main__':
    main()
