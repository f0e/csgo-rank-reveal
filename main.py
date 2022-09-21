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


def print_both(str=""):
    print(str)
    tn.write(f'echo "{str}"\n'.encode())


def print_game(str=""):
    tn.write(f'echo "{str}"\n'.encode())


def read_console(stop=[]):
    res = ""

    while True:
        data = tn.read_until(b"\n").decode("utf-8")
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
    tn.write(b"name\n")
    name_res = read_console()
    local_name = name_res.split('" ( def')[0].split('name" = "')[1]

    # get status
    tn.write(b"status\n")
    status_res = read_console(["#end", "Not connected to server"])

    # parse result
    lines = status_res.split("\r\n")
    players = []
    for line in lines:
        if not line.startswith("# "):
            continue

        if line == "# userid name uniqueid connected ping loss state rate":
            continue

        line = line.split("#")[1]

        # parse fields
        fields = []
        cur_field = ""
        in_str = False
        in_space = True
        for char in line:
            if char == '"':
                in_str = not in_str
                continue

            if not in_str:
                if char == " ":
                    if not in_space:
                        fields.append(cur_field)
                        cur_field = ""
                        in_space = True

                    continue

            cur_field += char
            in_space = False

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


def get_player_stats(id64):
    url = f"https://csgostats.gg/player/{id64}"
    stats_page = scraper.get(url)

    if (
        '<span style="font-size:24px; color:#fff; display:block; text-align:center;">No matches have been added for this player</span>'
        in stats_page.text
    ):
        return None

    soup = BeautifulSoup(stats_page.text, "html.parser")

    # get rank
    player_data = {"url": url}

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

    return player_data


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

    print_game()
    print_both("[rank reveal] ranks")

    scraper = cloudscraper.create_scraper()
    for i, player in enumerate(players):
        if player["self"]:
            continue

        print_both()

        id64 = Converter.to_steamID64(player["steamid"])
        player_stats = get_player_stats(id64)
        if not player_stats:
            print_both(f"{player['name']} | failed to get stats")
            continue

        # main details
        print_both(
            f"{player['name']} | {'rank' in player_stats and player_stats['rank'] or 'unranked'}"
        )

        # extra details
        extra_str = ""

        for key, value in player_stats.items():
            if key in ["rank"]:
                continue

            if extra_str != "":
                extra_str += ", "

            extra_str += f"{key}: {value}"

        if extra_str:
            print_both(extra_str)

    print_both()
    print_both("[rank reveal] done")
    print_game()
