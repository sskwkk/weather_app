from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ========== 配置你的API密钥（只改这三行）==========
BAIDU_AK = "maITzyXfUpj93nF3ZMp49WhFBL9fFWAS"
HEFENG_KEY = "0031128e58684a93b64af3a36411bc23"
GAODE_KEY = "799601c2ee85e4f58f8898ee6691df01"
HEFENG_HOST = "kc564vf68n.re.qweatherapi.com"   # 例如：abc123.re.qweatherapi.com
# ===============================================

# 初始化数据库
def init_db():
    conn = sqlite3.connect('weather.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS location_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT,
            timestamp DATETIME
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT,
            temp REAL,
            humidity REAL,
            aqi INTEGER,
            pm25 INTEGER,
            timestamp DATETIME
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# 首页路由
@app.route('/')
def index():
    return render_template('index.html')

# 接口1：获取/保存定位城市
@app.route('/api/location', methods=['GET', 'POST'])
def get_location():
    if request.method == 'POST':
        # GPS定位后保存城市
        city = request.args.get('city', '北京')
        conn = sqlite3.connect('weather.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO location_history (city, timestamp) VALUES (?, ?)',
                       (city, datetime.now()))
        conn.commit()
        conn.close()
        return jsonify({'code': 0, 'city': city})
    else:
        # GET请求：IP定位
        city = "北京"
        # 这里可以接入百度IP定位API
        conn = sqlite3.connect('weather.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO location_history (city, timestamp) VALUES (?, ?)',
                       (city, datetime.now()))
        conn.commit()
        conn.close()
        return jsonify({'code': 0, 'city': city})

# 接口2：获取天气和AQI
@app.route('/api/weather', methods=['GET'])
def get_weather():
    city = request.args.get('city', '北京')
    
    try:
        # 1. 获取城市经纬度
        geo_url = f"https://{HEFENG_HOST}/geo/v2/city/lookup?location={city}&key={HEFENG_KEY}"
        geo_resp = requests.get(geo_url)
        geo_data = geo_resp.json()
        
        if geo_data.get('code') != '200' or not geo_data.get('location'):
            return jsonify({'code': -1, 'msg': '城市查询失败'})
        
        loc = geo_data['location'][0]
        location_id = loc['id']
        lat = loc['lat']
        lon = loc['lon']
        
        # 2. 获取实时天气（和风天气）
        weather_url = f"https://{HEFENG_HOST}/v7/weather/now?location={location_id}&key={HEFENG_KEY}"
        weather_resp = requests.get(weather_url)
        weather_data = weather_resp.json()
        
        if weather_data.get('code') != '200':
            return jsonify({'code': -1, 'msg': '天气查询失败'})
        
        now = weather_data['now']
        
        # 3. 获取空气质量（和风天气）
        aqi_value = 'N/A'
        pm2p5_value = 'N/A'
        category_value = '暂无数据'
        
        try:
            air_url = f"https://{HEFENG_HOST}/airquality/v1/current/{lat}/{lon}?key={HEFENG_KEY}"
            air_resp = requests.get(air_url)
            air_data = air_resp.json()
            
            print(f"和风AQI返回: {air_data}")
            
            if air_data.get('indexes'):
                for index in air_data['indexes']:
                    if index.get('code') == 'cn-mee':
                        aqi_value = index.get('aqi', 'N/A')
                        category_value = index.get('category', '暂无数据')
                        break
                
                for p in air_data.get('pollutants', []):
                    if p.get('code') == 'pm2p5':
                        pm2p5_value = p.get('concentration', {}).get('value', 'N/A')
                        break
        except Exception as e:
            print(f"AQI获取失败: {e}")
        
        # 4. 组合结果
        result = {
            'city': city,
            'temp': now['temp'],
            'humidity': now['humidity'],
            'text': now['text'],
            'aqi': aqi_value,
            'pm2p5': pm2p5_value,
            'category': category_value
        }
        
        print(f"最终结果: {result}")
        
        # 5. 保存历史数据
        conn = sqlite3.connect('weather.db')
        cursor = conn.cursor()
        
        try:
            aqi_int = int(result['aqi']) if result['aqi'] != 'N/A' else 0
            pm25_int = int(float(result['pm2p5'])) if result['pm2p5'] != 'N/A' else 0
        except:
            aqi_int = 0
            pm25_int = 0
            
        cursor.execute('''
            INSERT INTO weather_history (city, temp, humidity, aqi, pm25, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (city, result['temp'], result['humidity'], aqi_int, pm25_int, datetime.now()))
        conn.commit()
        conn.close()
        
        return jsonify({'code': 0, 'data': result})
        
    except Exception as e:
        print(f"获取天气出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'code': -1, 'msg': f'服务异常: {str(e)}'})
# 接口3：获取历史数据
@app.route('/api/history', methods=['GET'])
def get_history():
    city = request.args.get('city', '北京')
    conn = sqlite3.connect('weather.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT temp, humidity, timestamp FROM weather_history 
        WHERE city = ? ORDER BY timestamp DESC LIMIT 7
    ''', (city,))
    rows = cursor.fetchall()
    conn.close()
    
    rows.reverse()
    temps = [row[0] for row in rows]
    humidities = [row[1] for row in rows]
    times = [row[2][5:16] for row in rows]
    
    return jsonify({
        'code': 0,
        'data': {'temps': temps, 'humidities': humidities, 'times': times}
    })
# 接口4：代理百度逆地理编码（解决CORS问题）
@app.route('/api/reverse_geo', methods=['GET'])
def reverse_geo():
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    
    if not lat or not lng:
        return jsonify({'code': -1, 'msg': '缺少经纬度参数'})
    
    url = f"https://api.map.baidu.com/reverse_geocoding/v3/?ak={BAIDU_AK}&output=json&coordtype=wgs84ll&location={lat},{lng}"
    
    try:
        resp = requests.get(url)
        data = resp.json()
        return jsonify(data)
    except Exception as e:
        return jsonify({'code': -1, 'msg': str(e)})
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)