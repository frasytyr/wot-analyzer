"""
WoT Replay Analyzer - сервер
Запуск: python server.py
Сайт откроется на http://localhost:5000
"""

import os
import json
import struct
import zlib
import pickle
import datetime
import traceback
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)

# ─── Карты (внутреннее имя → русское название) ────────────────────────────────
MAP_NAMES = {
    'north':            'Северный утёс',
    'south_coast':      'Южное побережье',
    'malinovka':        'Малиновка',
    'karelia':          'Карелия',
    'himmelsdorf':      'Химмельсдорф',
    'ensk':             'Энск',
    'lakeville':        'Лейквилль',
    'ruinberg':         'Руинберг',
    'mines':            'Рудники',
    'el_halluf':        'Эль-Халлуф',
    'murovanka':        'Мурованка',
    'cliff':            'Клиф',
    'sand_river':       'Песчаная река',
    'westfeld':         'Западный фронт',
    'campinovka':       'Кампиновка',
    'erlenberg':        'Эрленберг',
    'fisherman_bay':    "Fisherman's Bay",
    'redshire':         'Редшир',
    'steppes':          'Степи',
    'prokhorovka':      'Прохоровка',
    'fiery_salient':    'Огненный выступ',
    'airfield':         'Аэродром',
    'highway':          'Шоссе',
    'siegfried_line':   'Линия Зигфрида',
    'arctic_region':    'Арктический регион',
    'tundra':           'Тундра',
    'mountain_pass':    'Горный перевал',
    'live_oaks':        'Живые дубы',
    'hidden_village':   'Скрытая деревня',
    'serene_coast':     'Тихий берег',
    'paris':            'Париж',
    'minsk':            'Минск',
    'berlin':           'Берлин',
    'studzianki':       'Студзянки',
    'ghost_town':       'Призрак города',
    'empires_border':   'Граница империй',
    'outpost':          'Аванпост',
    'pearl_river':      'Жемчужная река',
    '05_prohorovka':    'Прохоровка',
    '02_malinovka':     'Малиновка',
    '04_himmelsdorf':   'Химмельсдорф',
    '07_lakeville':     'Лейквилль',
    '08_ruinberg':      'Руинберг',
    '10_hills':         'Холмы',
    '11_murovanka':     'Мурованка',
    '13_erlenberg':     'Эрленберг',
    '14_siegfried_line':'Линия Зигфрида',
    '15_redshire':      'Редшир',
    '17_campinovka':    'Кампиновка',
    '18_cliff':         'Клиф',
    '19_monastery':     'Монастырь',
    '22_slough':        'Болото',
    '23_westfeld':      'Западный фронт',
    '25_el_halluf':     'Эль-Халлуф',
    '28_desert_sands':  'Пустыня',
    '29_el_halluf':     'Эль-Халлуф',
    '31_airfield':      'Аэродром',
    '32_carthage':      'Карфаген',
    '33_fjord':         'Фьорды',
    '35_steppes':       'Степи',
    '36_fishing_bay':   "Fisherman's Bay",
    '38_mannerheim_line':'Линия Маннергейма',
    '39_crimea':        'Крым',
    '42_north_login':   'Северный утёс',
    '44_north_america': 'Северная Америка',
    '45_north_america': 'Северная Америка',
    '46_north_america': 'Северная Америка',
    '47_canada_a':      'Канада',
    '48_canada_a':      'Канада',
    '49_sandy_river':   'Песчаная река',
    '51_asia':          'Азия',
    '52_asia':          'Азия',
    '53_asia':          'Азия',
    '60_lion_city':     'Лионский город',
    '62_tutorial':      'Учебный',
    '63_tundra':        'Тундра',
    '64_medvedkovo':    'Медведково',
    '66_kharkov':       'Харьков',
    '67_heaven':        'Рай',
    '68_last_frontier': 'Последний рубеж',
    '69_arl_valley':    'Долина АРЛ',
    '70_wasteland':     'Пустошь',
    '73_nordic':        'Скандинавия',
    '74_decew_falls':   'Водопады Дэсю',
    '75_winter_himmelsdorf': 'Зимний Химмельсдорф',
    '76_refinery':      'Нефтеперегонный завод',
    '77_hamada':        'Хамада',
    '78_new_bay':       'Новая бухта',
    '79_highland':      'Высокогорье',
    '80_ruinberg_on_fire': 'Горящий Руинберг',
    '82_lost_city':     'Потерянный город',
    '83_kharkiv':       'Харьков',
    '84_winter_himmelsdorf': 'Зим. Химмельсдорф',
    '86_czechoslovakia':'Чехословакия',
    '87_new_colony':    'Новая колония',
    '88_coast':         'Побережье',
    '89_tank_grove':    'Танковый лес',
    '91_italy':         'Италия',
    '92_paris':         'Париж',
    '93_shooting_range':'Стрельбище',
    '95_lost_temple':   'Потерянный храм',
    '96_riverplace':    'Речной берег',
    '97_mali_lost':     'Мали',
    '98_prague':        'Прага',
    '99_mittengard':    'Миттенгард',
}

def map_name(internal):
    """Переводит внутреннее имя карты в читаемое"""
    if not internal:
        return 'Неизвестная карта'
    # Попробуем найти прямо
    key = internal.lower().strip()
    if key in MAP_NAMES:
        return MAP_NAMES[key]
    # Попробуем найти частичное совпадение
    for k, v in MAP_NAMES.items():
        if k in key or key in k:
            return v
    # Вернём исходное, убрав технические префиксы
    name = internal.replace('_', ' ').strip()
    if name and name[0].isdigit():
        parts = name.split(' ', 1)
        if len(parts) > 1:
            name = parts[1]
    return name.title() if name else 'Неизвестная карта'


# ─── Парсер .wotreplay ────────────────────────────────────────────────────────

def parse_wotreplay(file_bytes):
    """
    Структура .wotreplay:
      4 байта  — magic (0x12323411)
      4 байта  — количество JSON-блоков (обычно 1 или 2)
      Далее для каждого блока:
        4 байта — размер блока
        N байт  — JSON данные
      После всех блоков — бинарные данные игры (нас не интересуют)
    """
    if len(file_bytes) < 8:
        raise ValueError("Файл слишком маленький")

    magic = struct.unpack_from('<I', file_bytes, 0)[0]
    # Проверяем magic number
    if magic != 0x12323411:
        raise ValueError(f"Неверный формат файла (magic=0x{magic:08X})")

    block_count = struct.unpack_from('<I', file_bytes, 4)[0]

    if block_count < 1 or block_count > 10:
        raise ValueError(f"Неожиданное количество блоков: {block_count}")

    offset = 8
    blocks = []
    for i in range(block_count):
        if offset + 4 > len(file_bytes):
            break
        block_size = struct.unpack_from('<I', file_bytes, offset)[0]
        offset += 4
        if offset + block_size > len(file_bytes):
            break
        block_data = file_bytes[offset:offset + block_size]
        offset += block_size
        blocks.append(block_data)

    if not blocks:
        raise ValueError("Не найдено ни одного блока данных")

    # Блок 0 — данные начала боя (JSON)
    block0 = json.loads(blocks[0].decode('utf-8', errors='replace'))

    # Блок 1 — результаты боя (JSON, может отсутствовать в незавершённых реплеях)
    block1 = None
    if len(blocks) >= 2:
        try:
            block1 = json.loads(blocks[1].decode('utf-8', errors='replace'))
        except Exception:
            pass

    return block0, block1


def extract_battle_data(block0, block1, filename):
    """Извлекаем нужные данные из распарсенных блоков"""

    result = {
        'file': filename,
        'map': 'Неизвестная карта',
        'datetime': '',
        'result': 'UNKNOWN',
        'players': []
    }

    # ── Карта и время из блока 0 ──────────────────────────────────────────────
    try:
        map_internal = block0.get('mapName', '') or block0.get('mapDisplayName', '')
        result['map'] = map_name(map_internal)

        timestamp = block0.get('dateTime', '') or block0.get('dateTime', '')
        if not timestamp:
            # Попробуем из имени файла (формат: 20240315_1423_...)
            parts = filename.replace('.wotreplay', '').split('_')
            if len(parts) >= 2 and len(parts[0]) == 8:
                d = parts[0]
                t = parts[1]
                timestamp = f"{d[6:8]}.{d[4:6]}.{d[0:4]} {t[0:2]}:{t[2:4]}"
        result['datetime'] = timestamp
    except Exception:
        pass

    # ── Список игроков из блока 0 ─────────────────────────────────────────────
    players_in_battle = {}
    try:
        # vehicles / roster — список всех игроков в бою
        roster = block0.get('vehicles', {}) or block0.get('roster', {})
        for vid, vdata in roster.items():
            if isinstance(vdata, dict):
                nick = vdata.get('name', vdata.get('accountDBID', str(vid)))
                tank_tag = vdata.get('vehicleType', '') or vdata.get('typeCompDescr', '')
                # Убираем технический префикс страны (ussr:R04_T-34 → T-34)
                tank_name = tank_tag.split(':')[-1].split('-', 1)[-1] if ':' in tank_tag else tank_tag
                tank_name = tank_name.replace('_', ' ').strip() if tank_name else 'Неизвестный танк'
                players_in_battle[str(vid)] = {
                    'nick': nick,
                    'tank': tank_name,
                    'dmg': 0, 'assist': 0, 'kills': 0
                }
    except Exception:
        pass

    # ── Результаты игроков из блока 1 ─────────────────────────────────────────
    if block1:
        try:
            # Формат блока результатов может отличаться по версиям WoT
            vehicles = {}

            # Вариант 1: block1 — список [common, statistics, vehicles, ...]
            if isinstance(block1, list):
                for item in block1:
                    if isinstance(item, dict):
                        if 'vehicles' in item:
                            vehicles = item['vehicles']
                            break
                        # Иногда сам блок1[0] — это common info
                        if 'common' in item:
                            common = item['common']
                            win_reason = common.get('winnerTeam', 0)
                            # определяем команду игрока
                            player_team = block0.get('playerTeam', block0.get('team', 1))
                            if win_reason == 0:
                                result['result'] = 'DRAW'
                            elif win_reason == player_team:
                                result['result'] = 'WIN'
                            else:
                                result['result'] = 'LOSS'

            # Вариант 2: block1 — dict напрямую
            elif isinstance(block1, dict):
                vehicles = block1.get('vehicles', {})
                # Результат боя
                winner_team = block1.get('common', {}).get('winnerTeam', -1)
                if winner_team == 0:
                    result['result'] = 'DRAW'
                else:
                    player_team = block0.get('playerTeam', block0.get('team', 1))
                    if winner_team == player_team:
                        result['result'] = 'WIN'
                    else:
                        result['result'] = 'LOSS'

            # Обрабатываем статистику каждого игрока
            for vid, vlist in vehicles.items():
                # vlist может быть списком (несколько танков одного игрока) или dict
                vstat = vlist[0] if isinstance(vlist, list) and vlist else vlist
                if not isinstance(vstat, dict):
                    continue

                dmg    = vstat.get('damageDealt', 0) or 0
                assist = (vstat.get('damageAssistedTrack', 0) or 0) + \
                         (vstat.get('damageAssistedRadio', 0) or 0)
                kills  = vstat.get('kills', 0) or 0

                svid = str(vid)
                if svid in players_in_battle:
                    players_in_battle[svid]['dmg']    = dmg
                    players_in_battle[svid]['assist'] = assist
                    players_in_battle[svid]['kills']  = kills
                else:
                    # Пробуем найти по accountDBID
                    for k, p in players_in_battle.items():
                        if str(p.get('accountDBID', '')) == svid:
                            p['dmg']    = dmg
                            p['assist'] = assist
                            p['kills']  = kills
                            break

        except Exception as e:
            app.logger.warning(f"Ошибка разбора блока результатов: {e}")

    # ── Если результат всё ещё UNKNOWN — пробуем из имени файла ──────────────
    if result['result'] == 'UNKNOWN':
        fn_upper = filename.upper()
        if '_WIN_' in fn_upper or fn_upper.startswith('WIN'):
            result['result'] = 'WIN'
        elif '_LOSS_' in fn_upper or '_DEFEAT_' in fn_upper:
            result['result'] = 'LOSS'
        else:
            result['result'] = 'UNKNOWN'

    result['players'] = list(players_in_battle.values())
    return result


# ─── API роуты ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/parse', methods=['POST'])
def parse_replay():
    """Принимает один .wotreplay файл, возвращает JSON с данными боя"""
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'Пустое имя файла'}), 400

    try:
        file_bytes = f.read()
        block0, block1 = parse_wotreplay(file_bytes)
        data = extract_battle_data(block0, block1, f.filename)
        return jsonify({'ok': True, 'battle': data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e), 'file': f.filename}), 200


@app.route('/parse_many', methods=['POST'])
def parse_many():
    """Принимает несколько файлов, возвращает массив боёв"""
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'Файлы не найдены'}), 400

    results = []
    for f in files:
        try:
            file_bytes = f.read()
            block0, block1 = parse_wotreplay(file_bytes)
            data = extract_battle_data(block0, block1, f.filename)
            results.append({'ok': True, 'battle': data})
        except Exception as e:
            results.append({'ok': False, 'error': str(e), 'file': f.filename})

    return jsonify({'results': results})


# ─── Запуск ───────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
