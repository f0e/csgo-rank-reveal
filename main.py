import telnetlib
from steamid_converter import Converter
import cloudscraper
from bs4 import BeautifulSoup

HOST = "127.0.0.1"
PORT = 2121

RANK_NAMES = [
    "Silver I",
    "Silver II",
    "Silver III",
    "Silver IV",
    "Silver Elite",
    "Silver Elite Master",
    "Gold Nova I",
    "Gold Nova II",
    "Gold Nova III",
    "Gold Nova Master",
    "Master Guardian I",
    "Master Guardian II",
    "Master Guardian Elite",
    "Distinguished Master Guardian",
    "Legendary Eagle",
    "Legendary Eagle Master",
    "Supreme Master First Class",
    "The Global Elite",
]

tn = None


def connect():
    global tn
    tn = telnetlib.Telnet(HOST, PORT)


def read_console(stop=[]):
    res = ""

    while True:
        data = tn.read_until(b"\r\n").decode("utf-8")
        res += data

        if not stop:
            break

        line = data.strip()
        if type(stop) is list:
            if line in stop:
                break

        if type(stop) is str:
            if line == stop:
                break

    return res


def get_players():
    # get local name
    tn.write("name\n".encode("ascii"))
    name_res = read_console()
    local_name = name_res.split('" ( def')[0].split('name" = "')[1]

    # get status
    tn.write("status\n".encode("ascii"))
    status_res = read_console(["#end", "Not connected to server"])

    # parse result
    lines = status_res.split("\r\n")
    players = []
    for line in lines:
        if not line.startswith("# "):
            continue

        if line == "# userid name uniqueid connected ping loss state rate":
            continue

        line = line.split("# ")[1]

        # parse fields
        fields = []
        cur_field = ""
        in_str = False
        for char in line:
            if char == '"':
                in_str = not in_str
                continue

            if not in_str:
                if char == " ":
                    fields.append(cur_field)
                    cur_field = ""
                    continue

            cur_field += char

        if cur_field:
            fields.append(cur_field)

        # filter out gotv
        if fields[1] == "GOTV":
            continue

        # add player
        player = {
            "userid": f"{fields[0]} {fields[1]}",
            "name": fields[2].replace('"', ""),
            "steamid": fields[3],
            "time_connected": fields[4],
            "ping": fields[5],
            "loss": fields[6],
            "state": fields[7],
            "rate": fields[8],
        }

        player["self"] = player["name"] == local_name

        players.append(player)

    return players


if __name__ == "__main__":
    try:
        connect()
    except:
        print(f"failed to connect to csgo (game not open? -netconport {PORT} not set?)")
        quit()

    players = get_players()

    if not players:
        print("no players in server")
        quit()

    scraper = cloudscraper.create_scraper()
    for player in players:
        if player["self"]:
            continue

        id64 = Converter.to_steamID64(player["steamid"])
        url = f"https://csgostats.gg/player/{id64}"

        stats_page = scraper.get(url)

        if (
            '<span style="font-size:24px; color:#fff; display:block; text-align:center;">No matches have been added for this player</span>'
            in stats_page.text
        ):
            continue

        soup = BeautifulSoup(stats_page.text, "html.parser")

        # get rank
        player_data = {}

        rank_container = soup.find(class_="player-ranks")
        if rank_container:
            rank_images = rank_container.select("img[src]")

            def get_rank(index):
                if index >= len(rank_images):
                    return None

                image_src = rank_images[index]["src"]
                rank_index = int(image_src.split("ranks/")[1].split(".png")[0]) - 1
                return RANK_NAMES[rank_index]

            player_data["rank"] = get_rank(0)
            player_data["best_rank"] = get_rank(1)

        wins_container = soup.find(id="competitve-wins")
        if wins_container:
            player_data["wins"] = wins_container.find("span").text

        player_data["kd"] = soup.find(id="kpd").find("span").text
        player_data["rating"] = soup.find(id="rating").find("span").text

        print(f"{player['name']} | {player_data} | {url}")
