import argparse
import asyncio
import logging
import contextlib

import aiosip

proxy_ip = '0.0.0.0'
proxy_port = 6100

uas_host = 'sipuas'
uas_port = 6200

local_host = 'sipproxy'
local_port = 6300

pwd = 'xxxxxx'

def header(user, host, port) :
   return aiosip.Contact.from_header('sip:{}@{}:{}'.format( user, host,  port))

async def on_invite(request, message):
    dialog = await request.prepare(status_code=100)
    from_user = 'proxy'
    to_user = 'test'

    sip = aiosip.Application(loop=asyncio.get_event_loop())
    peer = await sip.connect((uas_host, uas_port), protocol=aiosip.TCP, local_addr=(local_host, local_port))

    call = await peer.invite(
               from_details=header(from_user, local_host, local_port),
               to_details=header(to_user, uas_host, uas_port),
               contact_details=header(from_user, local_host, local_port),
               password=pwd)

    async with call:
      async def reader():
          async for msg in call.wait_for_terminate():
              print("----------------CALL STATUS:", msg.status_code)
              await dialog.reply(message, status_code= msg.status_code)

      with contextlib.suppress(asyncio.TimeoutError):
         await asyncio.wait_for(reader(), timeout=10)

class Dialplan(aiosip.BaseDialplan):

    async def resolve(self, *args, **kwargs):
        await super().resolve(*args, **kwargs)

        if kwargs['method'] == 'INVITE':
            return on_invite


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
