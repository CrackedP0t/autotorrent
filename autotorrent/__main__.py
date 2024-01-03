from torf import Torrent
from qbittorrentapi import Client, exceptions
from notifypy import Notify
from urllib.parse import urlparse
import asyncio
import sys
import webbrowser
from jeepney import DBusAddress, new_method_call, MatchRule, message_bus, HeaderFields
from jeepney.io.asyncio import open_dbus_router, Proxy


async def main():
    notifications = DBusAddress(
        "/org/freedesktop/Notifications",
        bus_name="org.freedesktop.Notifications",
        interface="org.freedesktop.Notifications",
    )
    try:
        if len(sys.argv) != 2:
            raise Exception("Invalid arguments")

        QBT_URL = "http://seshat.lan:8080"

        client = Client(
            host=QBT_URL,
            username="admin",
            password="adminadmin",
            VERIFY_WEBUI_CERTIFICATE=False,
        )

        torrent = Torrent.read(sys.argv[1])

        tags = []
        category = None

        for t in torrent.trackers:
            for a in t:
                host = urlparse(a)[1].split(":")[0]
                if host == "tracker.tleechreload.org":
                    tags.append("TorrentLeech")
                if host == "nyaa.tracker.wf":
                    category = "Anime"

        videos = 0
        for f in torrent.files:
            if len(f.parents) <= 2 and f.suffix == ".mkv":
                videos += 1

        if videos == 1:
            category = "Movie"
        elif videos > 2:
            category = "TV"

        try:
            if client.torrents_properties(torrent.infohash):
                raise Exception("Torrent already added")
        except exceptions.NotFound404Error:
            pass

        client.torrents_add(torrent_files=[sys.argv[1]], category=category, tags=tags)

        match_rule_1 = MatchRule(
            type="signal",
            interface=notifications.interface,
            path=notifications.object_path,
            member="ActionInvoked",
        )
        match_rule_2 = MatchRule(
            type="signal",
            interface=notifications.interface,
            path=notifications.object_path,
            member="NotificationClosed",
        )

        msg = new_method_call(
            notifications,
            "Notify",
            "susssasa{sv}i",
            (
                "AutoTorrent",  # App name
                0,  # Not replacing any previous notification
                "qbittorrent",  # Icon
                "Added torrent",  # Summary
                f"Name: {torrent.name}\nCategory: {category}\nTags: {', '.join(tags) or 'None'}",
                ["default", "default"],
                {},  # Actions, hints
                -1,  # expire_timeout (-1 = default)
            ),
        )
        # Send the message and await the reply
        async with open_dbus_router() as router:
            reply = await router.send_and_get_reply(msg)

            await Proxy(message_bus, router).AddMatch(match_rule_1)
            await Proxy(message_bus, router).AddMatch(match_rule_2)

            queue = asyncio.Queue()
            router.filter(match_rule_1, queue=queue)
            router.filter(match_rule_2, queue=queue)
            while True:
                msg = await queue.get()
                match msg.header.fields[HeaderFields.member]:
                    case "ActionInvoked":
                        webbrowser.open(QBT_URL)
                    case "NotificationClosed":
                        break

    except Exception as e:
        msg = new_method_call(
            notifications,
            "Notify",
            "susssasa{sv}i",
            (
                "AutoTorrent",  # App name
                0,  # Not replacing any previous notification
                "dialog-error",  # Icon
                "Error adding torrent",  # Summary
                str(e),
                [],
                {},  # Actions, hints
                -1,  # expire_timeout (-1 = default)
            ),
        )
        async with open_dbus_router() as router:
            reply = await router.send(msg)

        with open("error.txt", "w") as f:
            import traceback

            f.write(traceback.format_exc())

        raise


asyncio.run(main())
