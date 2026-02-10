# ============================================
try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'google-ads'])
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException

import json, os, tempfile, hashlib, requests, re
from datetime import datetime

FILE_THRESHOLD_KB = 10
WARNING_THRESHOLD_TOKENS = 5000
STATE_DIR = '/tmp/gads_agent_state'
STATE_FILE = os.path.join(STATE_DIR, 'session_state.json')
FILES_DIR = os.path.join(STATE_DIR, 'files')

def get_client(login_customer_id=None):
    config = {'developer_token': secrets['DEVELOPER_TOKEN'], 'client_id': secrets['CLIENT_ID'], 'client_secret': secrets['CLIENT_SECRET'], 'refresh_token': secrets['REFRESH_TOKEN'], 'use_proto_plus': True}
    if login_customer_id: config['login_customer_id'] = str(login_customer_id).replace('-', '')
    return GoogleAdsClient.load_from_dict(config, version='v23')

def ensure_dirs():
    os.makedirs(STATE_DIR, exist_ok=True)
    os.makedirs(FILES_DIR, exist_ok=True)

def load_state():
    ensure_dirs()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f: return json.load(f)
        except: pass
    return {'files': {}, 'metrics': {'total_files_created': 0, 'bytes_offloaded': 0}}

def save_state(state):
    ensure_dirs()
    with open(STATE_FILE, 'w') as f: json.dump(state, f, indent=2, default=str)

def generate_id(prefix=''):
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
    hash_part = hashlib.md5(f"{timestamp}{os.urandom(8)}".encode()).hexdigest()[:8]
    return f"{prefix}{timestamp[:8]}_{hash_part}"

def calculate_size(data):
    json_str = json.dumps(data, default=str)
    size_bytes = len(json_str.encode('utf-8'))
    return {'bytes': size_bytes, 'kb': round(size_bytes / 1024, 2), 'estimated_tokens': size_bytes // 4}

def extract_searchable_metadata(data):
    index = {'entity_names': [], 'entity_ids': [], 'campaign_names': [], 'ad_group_names': [], 'account_names': [], 'keywords': [], 'stats': {}, 'record_count': 0}
    if not data: return index
    records = []
    if isinstance(data, dict):
        for key in ['campaigns', 'ad_groups', 'keywords', 'ads', 'accounts', 'budgets', 'audiences', 'assets', 'results', 'data']:
            if key in data and isinstance(data[key], list):
                records = data[key]; break
        if not records and 'status' in data: records = [data]
    elif isinstance(data, list): records = data
    index['record_count'] = len(records)
    for record in records:
        if not isinstance(record, dict): continue
        if 'campaign_name' in record: index['campaign_names'].append(record['campaign_name']); index['entity_names'].append(record['campaign_name'])
        if 'name' in record: index['entity_names'].append(record['name'])
        if 'campaign_id' in record: index['entity_ids'].append(str(record['campaign_id']))
        if 'ad_group_name' in record: index['ad_group_names'].append(record['ad_group_name']); index['entity_names'].append(record['ad_group_name'])
        if 'ad_group_id' in record: index['entity_ids'].append(str(record['ad_group_id']))
        if 'id' in record: index['entity_ids'].append(str(record['id']))
        if 'keyword' in record: index['keywords'].append(record['keyword'])
        for sf in ['cost', 'clicks', 'impressions', 'conversions', 'spend', 'budget']:
            if sf in record and isinstance(record[sf], (int, float)):
                if sf not in index['stats']: index['stats'][sf] = {'sum': 0, 'count': 0}
                index['stats'][sf]['sum'] += record[sf]; index['stats'][sf]['count'] += 1
    for k in ['entity_names', 'entity_ids', 'campaign_names', 'ad_group_names', 'account_names', 'keywords']:
        index[k] = list(set(filter(None, index[k])))
    return index

def generate_summary_stats(data_list):
    if not data_list or not isinstance(data_list[0], dict): return {}
    stats = {}
    numeric_fields = ['cost', 'clicks', 'impressions', 'conversions', 'cpc_bid', 'budget', 'cost_micros', 'cpc_bid_micros', 'budget_micros', 'amount_micros']
    for key in data_list[0].keys():
        values = [item.get(key) for item in data_list if isinstance(item.get(key), (int, float)) and key.lower() in [f.lower() for f in numeric_fields]]
        if values:
            is_micros = 'micros' in key.lower()
            d = 1000000 if is_micros else 1
            stats[key.replace('_micros', '')] = {'min': round(min(values)/d, 2), 'max': round(max(values)/d, 2), 'sum': round(sum(values)/d, 2), 'avg': round((sum(values)/len(values))/d, 2)}
    return stats

def write_to_managed_file(data, action_type, session_id=None, customer_id=None, ttl_hours=24):
    ensure_dirs()
    state = load_state()
    file_id = generate_id('file_')
    filename = f"{file_id}.json"
    managed_path = os.path.join(FILES_DIR, filename)
    with open(managed_path, 'w') as f: json.dump(data, f, indent=2, default=str)
    file_size = os.path.getsize(managed_path)
    from datetime import timedelta
    expires_at = (datetime.now() + timedelta(hours=ttl_hours)).isoformat()
    search_index = extract_searchable_metadata(data)
    if 'files' not in state: state['files'] = {}
    state['files'][file_id] = {'id': file_id, 'session_id': session_id, 'customer_id': customer_id, 'action_type': action_type, 'managed_path': managed_path, 'filename': filename, 'created_at': datetime.now().isoformat(), 'expires_at': expires_at, 'ttl_hours': ttl_hours, 'size_bytes': file_size, 'search_index': search_index, 'access_count': 0, 'last_accessed': None}
    if 'metrics' not in state: state['metrics'] = {'total_files_created': 0, 'bytes_offloaded': 0}
    state['metrics']['total_files_created'] += 1
    state['metrics']['bytes_offloaded'] += file_size
    save_state(state)
    return {'file_id': file_id, 'managed_path': managed_path, 'filename': filename, 'size_bytes': file_size, 'expires_at': expires_at, 'indexed': {'campaigns': len(search_index.get('campaign_names', [])), 'entities': len(search_index.get('entity_names', [])), 'records': search_index.get('record_count', 0)}}

def extract_data_and_type(result):
    data_mappings = [('campaigns','campaigns'),('ad_groups','ad_groups'),('keywords','keywords'),('ads','ads'),('budgets','budgets'),('negative_keywords','negative_keywords'),('audiences','audiences'),('assets','assets'),('labels','labels'),('conversion_actions','conversion_actions'),('experiments','experiments'),('drafts','drafts'),('accounts','accounts'),('results','results'),('data','data')]
    if isinstance(result, dict):
        for key, dtype in data_mappings:
            if key in result and isinstance(result[key], list): return result[key], dtype
        if result.get('status') == 'success': return [result], 'single_result'
    return [result] if not isinstance(result, list) else result, 'raw'

def run(action_type, action_params, session_id=None, max_preview_rows=5, force_file=False, ttl_hours=24):
    try:
        gateway_log = {'action_requested': action_type, 'params_received': {k: v for k, v in action_params.items() if k not in ['data', '_mock_result']}, 'timestamp': datetime.now().isoformat(), 'session_id': session_id}
        if '_mock_result' not in action_params:
            return {'status': 'info', 'message': 'Gateway ready. Pass API results via _mock_result parameter.'}
        result = action_params['_mock_result']
        size = calculate_size(result)
        data_list, data_type = extract_data_and_type(result)
        should_offload = force_file or size['kb'] > FILE_THRESHOLD_KB or len(data_list) > 10
        file_info = None
        if should_offload:
            customer_id = action_params.get('customer_id') or action_params.get('search')
            file_result = write_to_managed_file(data=result, action_type=action_type, session_id=session_id, customer_id=customer_id, ttl_hours=ttl_hours)
            file_info = {'offloaded': True, 'file_id': file_result['file_id'], 'managed_path': file_result['managed_path'], 'filename': file_result['filename'], 'expires_at': file_result['expires_at'], 'indexed': file_result['indexed'], 'retrieval_instruction': f"Use file_search with file_id='{file_result['file_id']}'"}
        preview = {'data_type': data_type, 'total_count': len(data_list) if isinstance(data_list, list) else 1, 'preview_rows': data_list[:max_preview_rows] if isinstance(data_list, list) else data_list, 'has_more': len(data_list) > max_preview_rows if isinstance(data_list, list) else False, 'rows_omitted': max(0, len(data_list) - max_preview_rows) if isinstance(data_list, list) else 0}
        if isinstance(data_list, list) and len(data_list) > 0:
            stats = generate_summary_stats(data_list)
            if stats: preview['summary_stats'] = stats
        context_impact = 'MINIMAL' if should_offload else 'LOW' if size['estimated_tokens'] < 1000 else 'MODERATE' if size['estimated_tokens'] < WARNING_THRESHOLD_TOKENS else 'HIGH'
        response = {'status': 'success', 'gateway_processed': True, 'action': action_type, 'session_id': session_id, 'size_metrics': size, 'context_impact': context_impact, 'preview': preview}
        if file_info: response['file_storage'] = file_info; response['next_step'] = 'Data saved to managed storage.'
        return response
    except Exception as e:
        return {'status': 'error', 'message': str(e), 'action_attempted': action_type}
