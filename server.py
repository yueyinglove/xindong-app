import os, json, random, glob, datetime
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

XINDONG_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(XINDONG_DIR, exist_ok=True)


@app.route('/sf-tts/audio/speech', methods=['POST'])
def sf_tts_proxy():
    import requests as req
    headers = {
        'Content-Type': 'application/json',
        'Authorization': request.headers.get('Authorization', '')
    }
    try:
        r = req.post('https://api.siliconflow.cn/v1/audio/speech',
                      json=request.get_json(force=True),
                      headers=headers, timeout=60)
        from flask import Response
        return Response(r.content, status=r.status_code,
                        content_type=r.headers.get('Content-Type', 'audio/mpeg'))
    except Exception as e:
        return jsonify({'error': str(e)}), 502

@app.route('/')
def index():
    return send_from_directory('.', 'xindong.html')

@app.route('/xindong/api/create', methods=['POST'])
def xindong_create():
    data = request.get_json(force=True)
    quiz_id = data.get('quiz_id', '')
    title = data.get('title', '问卷')
    questions = data.get('questions', [])
    my_name = data.get('my_name', '我')
    your_name = data.get('your_name', '')
    if not quiz_id:
        return jsonify({'error': '缺少 quiz_id'}), 400
    pair_code = str(random.randint(1000, 9999))
    session = {
        'quiz_id': quiz_id,
        'title': title,
        'questions': questions,
        'my_name': my_name,
        'your_name': your_name,
        'human_answers': {},
        'ai_answers': {},
        'human_done': False,
        'ai_done': False,
        'created_at': datetime.datetime.now().isoformat(),
        'merged': False,
        'pair_code': pair_code,
        'ai_connected': False
    }
    path = os.path.join(XINDONG_DIR, quiz_id + '.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(session, f, ensure_ascii=False, indent=2)
    return jsonify({'ok': True, 'quiz_id': quiz_id, 'pair_code': pair_code})

@app.route('/xindong/api/connect', methods=['POST'])
def xindong_connect():
    data = request.get_json(force=True)
    quiz_id = data.get('quiz_id', '')
    pair_code = data.get('pair_code', '')
    ai_name = data.get('ai_name', '')
    if not quiz_id or not pair_code:
        return jsonify({'error': '缺少 quiz_id 或 pair_code'}), 400
    path = os.path.join(XINDONG_DIR, quiz_id + '.json')
    if not os.path.exists(path):
        return jsonify({'error': '问卷不存在'}), 404
    with open(path, 'r', encoding='utf-8') as f:
        session = json.load(f)
    if session.get('pair_code') != pair_code:
        return jsonify({'error': '配对码不正确'}), 403
    session['ai_connected'] = True
    if ai_name:
        session['your_name'] = ai_name
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(session, f, ensure_ascii=False, indent=2)
    return jsonify({'ok': True, 'message': 'AI已连接', 'questions': session['questions'], 'title': session['title']})

@app.route('/xindong/api/submit', methods=['POST'])
def xindong_submit():
    data = request.get_json(force=True)
    quiz_id = data.get('quiz_id', '')
    who = data.get('who', '')
    answers = data.get('answers', {})
    if not quiz_id or who not in ('human', 'ai'):
        return jsonify({'error': '缺少 quiz_id 或 who 参数'}), 400
    path = os.path.join(XINDONG_DIR, quiz_id + '.json')
    if not os.path.exists(path):
        return jsonify({'error': '问卷不存在'}), 404
    with open(path, 'r', encoding='utf-8') as f:
        session = json.load(f)
    if who == 'human':
        session['human_answers'] = answers
        session['human_done'] = True
    else:
        session['ai_answers'] = answers
        session['ai_done'] = True
    session['merged'] = session['human_done'] and session['ai_done']
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(session, f, ensure_ascii=False, indent=2)
    return jsonify({
        'ok': True,
        'human_done': session['human_done'],
        'ai_done': session['ai_done'],
        'merged': session['merged']
    })

@app.route('/xindong/api/status', methods=['GET'])
def xindong_status():
    quiz_id = request.args.get('quiz_id', '')
    if not quiz_id:
        return jsonify({'error': '缺少 quiz_id'}), 400
    path = os.path.join(XINDONG_DIR, quiz_id + '.json')
    if not os.path.exists(path):
        return jsonify({'error': '问卷不存在', 'exists': False}), 404
    with open(path, 'r', encoding='utf-8') as f:
        session = json.load(f)
    result = {
        'exists': True,
        'quiz_id': session['quiz_id'],
        'title': session['title'],
        'questions': session['questions'],
        'my_name': session['my_name'],
        'your_name': session['your_name'],
        'human_done': session['human_done'],
        'ai_done': session['ai_done'],
        'merged': session['merged'],
        'ai_connected': session.get('ai_connected', False)
    }
    if session['ai_done']:
        result['ai_answers'] = session['ai_answers']
    if session['human_done']:
        result['human_answers'] = session['human_answers']
    return jsonify(result)

@app.route('/xindong/api/list', methods=['GET'])
def xindong_list():
    files = sorted(glob.glob(os.path.join(XINDONG_DIR, '*.json')), key=os.path.getmtime, reverse=True)
    result = []
    for fp in files:
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                session = json.load(f)
            result.append({
                'quiz_id': session['quiz_id'],
                'title': session['title'],
                'human_done': session['human_done'],
                'ai_done': session['ai_done'],
                'merged': session['merged'],
                'created_at': session.get('created_at', '')
            })
        except:
            pass
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
