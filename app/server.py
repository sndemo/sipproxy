import argparse
import asyncio
import logging
import contextlib
import aioredis
import aiosip
import json
import random

proxy_ip = '0.0.0.0'
proxy_port = 6100

uas_host = 'sipuas'
uas_port = 6200

registrar_host = 'sipregistrar'
registrar_port = 6000

local_host = 'sipproxy'

pwd = 'xxxxxx'


async def get_address(user):
    redis = await aioredis.create_redis('redis://redis')
    key = 'user:address:'+user
    value = await redis.get(key)
    
    if not value :
        return None, None

    print('Address raw value from Redis:', value)
    address = json.loads(await redis.get(key))
    print('address from Redis (key, address)', key, address)
    
    redis.close()
    await redis.wait_closed()

    return address['host'], address['port']

def header(user, host, port) :
   return aiosip.Contact.from_header('sip:{}@{}:{}'.format( user, host,  port))

async def on_invite(request, message):
    dialog = await request.prepare(status_code=100)
    
    to_uri = message.to_details['uri']
    to_user = to_uri['user']
    to_host, to_port = await get_address(to_user)
    
    if not to_host :
       not_found_message = "User {} is not registered.".format(to_user)
       print(not_found_message)
       #await dialog.reply(message, status_code= 404, status_message=not_found_message)
       await dialog.reply(message, 404)
       async for message in dialog:
                await dialog.reply(message, 404)
       return
    
    loop = asyncio.get_event_loop()
    sip = aiosip.Application(loop=loop)

    local_port = random.randint(6001, 6999)
    peer = await sip.connect((to_host, to_port), protocol=aiosip.TCP, local_addr=(local_host, local_port))

    call = await peer.invite(
               from_details= message.from_details,
               to_details= message.to_details,
               contact_details= message.contact_details,
               password=pwd)

    async with call:
      async def reader():
          async for msg in call.wait_for_terminate():
              print("CALL STATUS:", msg.status_code)
              await dialog.reply(message, status_code= msg.status_code)

      with contextlib.suppress(asyncio.TimeoutError):
         await asyncio.wait_for(reader(), timeout=10)
    
    await sip.close()
    loop.close()

async def on_register(request, message):
    dialog = await request.prepare(status_code=100)
    
    loop = asyncio.get_event_loop()
    sip = aiosip.Application(loop=loop)

    local_port = random.randint(7001,7999)
    peer = await sip.connect((registrar_host, registrar_port), protocol=aiosip.TCP, local_addr=(local_host, local_port))

    rdialog = await peer.register(
               from_details=message.from_details,
               to_details=message.to_details,
               contact_details=message.contact_details,
               password=pwd)

    print("Registrar response:", rdialog.status_code)
    await dialog.reply(message, status_code= rdialog.status_code)
    
    await sip.close()
    loop.close()


class Dialplan(aiosip.BaseDialplan):

    async def resolve(self, *args, **kwargs):
        await super().resolve(*args, **kwargs)

        if kwargs['method'] == 'INVITE':
            return on_invite
        
        if kwargs['method'] == 'REGISTER':
            return on_register


def start(app, protocol):
    app.loop.run_until_complete( app.run(  protocol=protocol, local_addr=(proxy_ip, proxy_port)))
    print('Serving on {} {}'.format( (proxy_ip, proxy_port), protocol))

    try:
        app.loop.run_forever()
    except KeyboardInterrupt:
        pass

    print('Closing')
    app.loop.run_until_complete(app.close())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--protocol', default='tcp')
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    app = aiosip.Application(loop=loop, dialplan=Dialplan())

    if args.protocol == 'udp':
        start(app, aiosip.UDP)
    elif args.protocol == 'tcp':
        start(app, aiosip.TCP)
    elif args.protocol == 'ws':
        start(app, aiosip.WS)
    else:
        raise RuntimeError("Unsupported protocol: {}".format(args.protocol))

    loop.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
