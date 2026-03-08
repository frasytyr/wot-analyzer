"""
WoT Replay Analyzer - сервер
Протестировано на WoT v2.2.0.0
"""

import os, json, struct, re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB на файл
CORS(app)

# ─── Имена карт ───────────────────────────────────────────────────────────────
MAP_NAMES = {
    '01_karelia': 'Карелия', '02_malinovka': 'Малиновка',
    '03_campania': 'Кампания', '04_himmelsdorf': 'Химмельсдорф',
    '05_prohorovka': 'Прохоровка', '06_ensk': 'Энск',
    '07_lakeville': 'Лейквилль', '08_ruinberg': 'Руинберг',
    '10_hills': 'Рудники', '11_murovanka': 'Мурованка',
    '13_erlenberg': 'Эрленберг', '14_siegfried_line': 'Линия Зигфрида',
    '15_redshire': 'Редшир', '17_campinovka': 'Кампиновка',
    '18_cliff': 'Клиф', '19_monastery': 'Монастырь',
    '22_slough': 'Болото', '23_westfeld': 'Западный фронт',
    '25_el_halluf': 'Эль-Халлуф', '28_desert_sands': 'Пустыня',
    '31_airfield': 'Аэродром', '33_fjord': 'Фьорды',
    '35_steppes': 'Степи', '36_fishing_bay': "Fisherman's Bay",
    '38_mannerheim_line': 'Линия Маннергейма', '42_north_login': 'Северный утёс',
    '44_north_america': 'Сев. Америка', '49_sandy_river': 'Песчаная река',
    '51_asia': 'Азия', '60_lion_city': 'Лионский город',
    '63_tundra': 'Тундра', '66_kharkov': 'Харьков',
    '70_wasteland': 'Пустошь', '73_nordic': 'Скандинавия',
    '75_winter_himmelsdorf': 'Зим. Химмельсдорф', '76_refinery': 'НПЗ',
    '77_hamada': 'Хамада', '78_new_bay': 'Новая бухта',
    '79_highland': 'Высокогорье', '82_lost_city': 'Потерянный город',
    '86_czechoslovakia': 'Чехословакия', '87_new_colony': 'Новая колония',
    '88_coast': 'Побережье', '91_italy': 'Италия',
    '92_paris': 'Париж', '95_lost_temple': 'Потерянный храм',
    '96_riverplace': 'Речной берег', '98_prague': 'Прага',
    '99_mittengard': 'Миттенгард',
}

def get_map_name(map_name_raw, map_display_name):
    # Сначала пробуем mapDisplayName (уже по-русски)
    if map_display_name:
        return map_display_name
    if not map_name_raw:
        return 'Неизвестная карта'
    key = map_name_raw.lower().strip()
    if key in MAP_NAMES:
        return MAP_NAMES[key]
    # частичный поиск
    for k, v in MAP_NAMES.items():
        if k in key:
            return v
    return map_name_raw.replace('_', ' ').title()

def clean_tank_name(vehicle_type):
    """czech:Cz21_Vz_60S_Dravec  →  Vz 60S Dravec"""
    if not vehicle_type:
        return 'Неизвестный танк'
    t = vehicle_type.split(':', 1)[-1]          # убираем czech:
    t = re.sub(r'^[A-Za-z]+\d+_', '', t)        # убираем Cz21_
    return t.replace('_', ' ').strip() or 'Неизвестный танк'

# ─── Парсер ───────────────────────────────────────────────────────────────────
def parse_wotreplay(file_bytes):
    if len(file_bytes) < 8:
        raise ValueError("Файл слишком маленький")

    magic = struct.unpack_from('<I', file_bytes, 0)[0]
    if magic != 0x11343212:
        raise ValueError(f"Неверный magic: 0x{magic:08X} (ожидался 0x11343212)")

    block_count = struct.unpack_from('<I', file_bytes, 4)[0]
    if block_count < 1 or block_count > 10:
        raise ValueError(f"Неожиданное количество блоков: {block_count}")

    offset = 8
    blocks = []
    for _ in range(block_count):
        if offset + 4 > len(file_bytes):
            break
        bsize = struct.unpack_from('<I', file_bytes, offset)[0]
        offset += 4
        if offset + bsize > len(file_bytes):
            break
        blocks.append(json.loads(file_bytes[offset:offset + bsize].decode('utf-8', errors='replace')))
        offset += bsize

    if not blocks:
        raise ValueError("Не найдено ни одного блока данных")

    return blocks[0], blocks[1] if len(blocks) >= 2 else None


def extract_battle(b0, b1, filename):
    result = {
        'file': filename,
        'map': get_map_name(b0.get('mapName', ''), b0.get('mapDisplayName', '')),
        'datetime': b0.get('dateTime', ''),
        'result': 'UNKNOWN',
        'players': []
    }

    # Если дата не в реплее — берём из имени файла (20260305_2308_...)
    if not result['datetime']:
        m = re.match(r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})', filename)
        if m:
            result['datetime'] = f"{m[3]}.{m[2]}.{m[1]} {m[4]}:{m[5]}"

    # ── Ростер игроков из b0['vehicles'] ─────────────────────────────────────
 # Сначала определяем команду главного игрока
    player_name = b0.get('playerName', '')
    player_team = None
    if b1 and isinstance(b1, list) and len(b1) >= 1:
        for pid, pdata in b1[0].get('players', {}).items():
            if pdata.get('name') == player_name:
                player_team = pdata.get('team')
                break

    # Берём только союзников (та же команда)
    roster = {}
    for vid, vdata in b0.get('vehicles', {}).items():
        team = vdata.get('team')
        if player_team is not None and team != player_team:
            continue  # пропускаем врагов
        name = vdata.get('fakeName') or vdata.get('name') or f'Player_{vid}'
        tank = clean_tank_name(vdata.get('vehicleType', ''))
        roster[str(vid)] = {'nick': name, 'tank': tank, 'team': team,
                             'dmg': 0, 'assist': 0, 'kills': 0}

    # ── Данные из b1 ─────────────────────────────────────────────────────────
    player_team = None
    if b1 and isinstance(b1, list) and len(b1) >= 1:
        summary = b1[0]   # {'personal', 'players', 'vehicles', 'common', ...}

        # Определяем команду главного игрока через b1[0]['players']
        player_id = str(b0.get('playerID', ''))
        players_info = summary.get('players', {})
        for pid, pdata in players_info.items():
            if pdata.get('name') == b0.get('playerName') or str(pid) == player_id:
                player_team = pdata.get('team')
                break

        # Результат боя
        common = summary.get('common', {})
        winner_team = common.get('winnerTeam')
        if winner_team == 0:
            result['result'] = 'DRAW'
        elif player_team and winner_team == player_team:
            result['result'] = 'WIN'
        elif player_team and winner_team != player_team:
            result['result'] = 'LOSS'
        else:
            result['result'] = 'UNKNOWN'

        # Статистика по машинам
        vehicles_stats = summary.get('vehicles', {})
        for vid, vlist in vehicles_stats.items():
            vstat = vlist[0] if isinstance(vlist, list) and vlist else vlist
            if not isinstance(vstat, dict):
                continue
            svid = str(vid)
            if svid in roster:
                roster[svid]['dmg']    = vstat.get('damageDealt', 0) or 0
                roster[svid]['assist'] = (vstat.get('damageAssistedRadio', 0) or 0) + \
                                         (vstat.get('damageAssistedTrack', 0) or 0)
                roster[svid]['kills']  = vstat.get('kills', 0) or 0

    result['players'] = list(roster.values())
    return result


# ─── API ──────────────────────────────────────────────────────────────────────
@app.route('/ping')
def ping():
    return 'ok', 200
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/parse', methods=['POST'])
def parse_replay():
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'Файл не найден'}), 400
    f = request.files['file']
    try:
        b0, b1 = parse_wotreplay(f.read())
        battle  = extract_battle(b0, b1, f.filename)
        return jsonify({'ok': True, 'battle': battle})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e), 'file': f.filename})

@app.route('/parse_many', methods=['POST'])
def parse_many():
    files = request.files.getlist('files')
    results = []
    for f in files:
        try:
            b0, b1 = parse_wotreplay(f.read())
            battle  = extract_battle(b0, b1, f.filename)
            results.append({'ok': True, 'battle': battle})
        except Exception as e:
            results.append({'ok': False, 'error': str(e), 'file': f.filename})
    return jsonify({'results': results})

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
