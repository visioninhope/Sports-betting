"""
Winamax odds scraper
"""

from collections import defaultdict
import datetime
import json
import urllib
import urllib.error
import urllib.request

from bs4 import BeautifulSoup

import sportsbetting as sb
from sportsbetting.database_functions import (
    is_player_in_db, add_player_to_db, is_player_added_in_db,
    add_new_player_to_db, is_in_db_site, get_formatted_name_by_id
)

def parse_winamax(url):
    """
    Retourne les cotes disponibles sur winamax
    """
    ids = url.split("/sports/")[1]
    try:
        tournament_id = int(ids.split("/")[2])
    except IndexError:
        tournament_id = -1
    sport_id = int(ids.split("/")[0])
    try:
        req = urllib.request.Request(url, headers = { 'User-Agent': 'Mozilla/5.0' })
        webpage = urllib.request.urlopen(req, timeout=10).read()
        soup = BeautifulSoup(webpage, features="lxml")
    except urllib.error.HTTPError:
        raise sb.UnavailableSiteException
    match_odds_hash = {}
    for line in soup.find_all(['script']):
        if "PRELOADED_STATE" not in str(line.string):
            continue
        json_text = (line.string.split("var PRELOADED_STATE = ")[1]
                     .split(";var BETTING_CONFIGURATION")[0])
        if json_text[-1] == ";":
            json_text = json_text[:-1]
        dict_matches = json.loads(json_text)
        if "matches" not in dict_matches:
            continue
        for match in dict_matches["matches"].values():
            if (tournament_id in (match['tournamentId'], -1) and match["competitor1Id"] != 0
                    and match['sportId'] == sport_id and 'isOutright' not in match.keys()):
                try:
                    match_name = match["title"].strip().replace("  ", " ")
                    date_time = datetime.datetime.fromtimestamp(match["matchStart"])
                    if date_time < datetime.datetime.today():
                        continue
                    main_bet_id = match["mainBetId"]
                    odds_ids = dict_matches["bets"][str(
                        main_bet_id)]["outcomes"]
                    odds = [dict_matches["odds"]
                            [str(x)] for x in odds_ids]
                    if not all(odds):
                        odds = []
                    match_odds_hash[match_name] = {
                        'odds' : {"winamax": odds},
                        'date' : date_time,
                        'id' : {"winamax": str(match["matchId"])},
                        'competition' : (
                            dict_matches["tournaments"]
                            [str(match['tournamentId'])]["tournamentName"]
                        )
                    }
                except KeyError:
                    pass
        if not match_odds_hash:
            raise sb.UnavailableCompetitionException
        return match_odds_hash
    raise sb.UnavailableSiteException

def get_sub_markets_players_basketball_winamax(id_match):
    """
    Get submarkets odds from basketball match
    """
    if not id_match:
        return {}
    url = 'https://www.winamax.fr/paris-sportifs/match/' + id_match
    try:
        req = urllib.request.Request(url)
        webpage = urllib.request.urlopen(req, timeout=10).read()
        soup = BeautifulSoup(webpage, features='lxml')
    except urllib.error.HTTPError:
        raise sb.UnavailableSiteException
    markets_to_keep = {
        '4436':'Points + passes + rebonds',
        '4437':'Passes',
        '4438':'Rebonds',
        '4971':'Points + passes + rebonds',
        '4970':'Passes',
        '4969':'Rebonds',
        '4442':'Points',
        '4968':'Points',
        '4434':'3 Points',
        '4433':'3 Points',
        '4432':'3 Points',
        '5423':'Points + rebonds',
        '5421':'Points + rebonds',
        '5424':'Points + passes',
        '5425':'Points + passes',
        '5426':'Passes + rebonds',
        '5427':'Passes + rebonds',
    }
    sub_markets = {v:defaultdict(list) for v in markets_to_keep.values()}
    for line in soup.find_all(['script']):
        if 'PRELOADED_STATE' not in str(line.string):
            continue
        json_text = line.string.split('var PRELOADED_STATE = ')[1].split(';var BETTING_CONFIGURATION')[0]
        if json_text[(-1)] == ';':
            json_text = json_text[:-1]
        dict_matches = json.loads(json_text)
        for bet in dict_matches['bets'].values():
            if str(bet['betType']) not in markets_to_keep:
                continue
            id_team = is_in_db_site(bet['betTitle'].split(" par ")[-1], "basketball", "winamax")
            if id_team:
                ref_player = get_formatted_name_by_id(id_team[0])
            limit = bet['specialBetValue'].split("sbv=")[-1].replace(",", ".")
            is_3_pts = bet['marketId'] in [9021, 9022]
            if bet["marketId"] == 9020:
                ref_player = "Match"
                is_3_pts = True
            id_outcomes = bet['outcomes']
            for id_outcome in id_outcomes:
                odd = dict_matches['odds'][str(id_outcome)]
                if not is_3_pts:
                    label = dict_matches['outcomes'][str(id_outcome)]['label']
                    code = dict_matches['outcomes'][str(id_outcome)]['code']
                    player = label.split(' - ')[0].split()[1]
                    limit = code.split('_')[(-1)].replace(",", ".")
                    player = label.split(' - ')[0].split('- Plus de ')[0].strip()
                    ref_player = player
                    if is_player_added_in_db(player, "winamax"):
                        ref_player = is_player_added_in_db(player, "winamax")
                    elif is_player_in_db(player):
                        add_player_to_db(player, "winamax")
                    else:
                        if sb.DB_MANAGEMENT:
                            print("nouveau joueur : ", player, "winamax")
                            add_new_player_to_db(player)
                        else:
                            continue
                key_player = ref_player + "_" + limit
                key_market = markets_to_keep[str(bet['betType'])]
                if key_player not in sub_markets[key_market]:
                    sub_markets[key_market][key_player] = {"odds":{"winamax":[]}}
                if not odd:
                    odd = 1.01
                sub_markets[key_market][key_player]["odds"]["winamax"].append(odd)
                if key_market == "Points":
                    sub_markets[key_market][key_player]["odds"]["winamax"].append(1.01)
    for sub_market in sub_markets:
        sub_markets[sub_market] = dict(sub_markets[sub_market])
    return dict(sub_markets)
