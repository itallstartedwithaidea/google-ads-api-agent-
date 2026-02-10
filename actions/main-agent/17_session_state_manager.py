# ============================================
import json, os, hashlib, shutil, re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

STATE_DIR = '/tmp/gads_agent_state'
STATE_FILE = os.path.join(STATE_DIR, 'session_state.json')
FILES_DIR = os.path.join(STATE_DIR, 'files')
DEFAULT_FILE_TTL_HOURS = 24
DEFAULT_PLAN_TTL_HOURS = 4

def ensure_dirs(): os.makedirs(STATE_DIR, exist_ok=True); os.makedirs(FILES_DIR, exist_ok=True)

def load_state():
    ensure_dirs()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f: return json.load(f)
        except: pass
    return create_empty_state()

def save_state(state):
    ensure_dirs()
    state['updated_at'] = datetime.now().isoformat()
    with open(STATE_FILE, 'w') as f: json.dump(state, f, indent=2, default=str)

def create_empty_state():
    return {'version': '3.0', 'created_at': datetime.now().isoformat(), 'updated_at': datetime.now().isoformat(), 'sessions': {}, 'session_names': {}, 'files': {}, 'operations': {}, 'handoffs': {}, 'search_index': {}, 'query_plans': {}, 'sub_agent_states': {}, 'context_usage': {}, 'metrics': {'total_files_created': 0, 'total_operations': 0, 'total_handoffs': 0, 'bytes_offloaded': 0, 'query_plans_cached': 0, 'context_tokens_saved': 0}}

def generate_id(prefix=''):
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
    hash_part = hashlib.md5(f"{timestamp}{os.urandom(8)}".encode()).hexdigest()[:8]
    return f"{prefix}{timestamp[:8]}_{hash_part}"

def normalize_name(name): return re.sub(r'[^a-z0-9]', '', name.lower())

def cache_query_plan(session_id, plan_name, query_plan, ttl_hours=DEFAULT_PLAN_TTL_HOURS):
    state = load_state()
    if 'query_plans' not in state: state['query_plans'] = {}
    plan_id = generate_id('plan_')
    plan_key = f"{session_id}:{normalize_name(plan_name)}"
    state['query_plans'][plan_key] = {'plan_id': plan_id, 'session_id': session_id, 'name': plan_name, 'query_plan': query_plan, 'created_at': datetime.now().isoformat(), 'expires_at': (datetime.now() + timedelta(hours=ttl_hours)).isoformat(), 'used_count': 0, 'last_used': None}
    state['metrics']['query_plans_cached'] = state['metrics'].get('query_plans_cached', 0) + 1
    save_state(state)
    return {'status': 'success', 'plan_id': plan_id, 'plan_key': plan_key}

def get_cached_plan(session_id, plan_name):
    state = load_state()
    plan_key = f"{session_id}:{normalize_name(plan_name)}"
    if plan_key not in state.get('query_plans', {}): return {'status': 'not_found'}
    plan = state['query_plans'][plan_key]
    if datetime.fromisoformat(plan['expires_at']) < datetime.now():
        del state['query_plans'][plan_key]; save_state(state); return {'status': 'expired'}
    plan['used_count'] += 1; plan['last_used'] = datetime.now().isoformat(); save_state(state)
    return {'status': 'success', 'plan_id': plan['plan_id'], 'query_plan': plan['query_plan']}

def sync_sub_agent_state(handoff_id, sub_agent_id, status='started', current_step=None, progress_percent=0):
    state = load_state()
    if 'sub_agent_states' not in state: state['sub_agent_states'] = {}
    state['sub_agent_states'][handoff_id] = {'handoff_id': handoff_id, 'sub_agent_id': sub_agent_id, 'status': status, 'current_step': current_step, 'progress_percent': progress_percent, 'updated_at': datetime.now().isoformat(), 'started_at': state['sub_agent_states'].get(handoff_id, {}).get('started_at', datetime.now().isoformat())}
    save_state(state)
    return {'status': 'success', 'synced': True}

def receive_sub_agent_result(handoff_id, result_summary, file_id=None, tokens_used=0, error=None):
    state = load_state()
    if handoff_id in state.get('sub_agent_states', {}):
        state['sub_agent_states'][handoff_id]['status'] = 'failed' if error else 'completed'
        state['sub_agent_states'][handoff_id]['completed_at'] = datetime.now().isoformat()
    result_id = generate_id('result_')
    if 'sub_agent_results' not in state: state['sub_agent_results'] = {}
    state['sub_agent_results'][handoff_id] = {'result_id': result_id, 'handoff_id': handoff_id, 'result_summary': result_summary, 'file_id': file_id, 'tokens_used': tokens_used, 'error': error, 'received_at': datetime.now().isoformat()}
    save_state(state)
    return {'status': 'success', 'result_id': result_id}

def track_context_usage(session_id, agent_type, action, tokens_used, tokens_saved=0):
    state = load_state()
    if 'context_usage' not in state: state['context_usage'] = {}
    if session_id not in state['context_usage']: state['context_usage'][session_id] = {'total_tokens_used': 0, 'total_tokens_saved': 0, 'entries': []}
    state['context_usage'][session_id]['total_tokens_used'] += tokens_used
    state['context_usage'][session_id]['total_tokens_saved'] += tokens_saved
    state['context_usage'][session_id]['entries'].append({'agent_type': agent_type, 'action': action, 'tokens_used': tokens_used, 'tokens_saved': tokens_saved, 'timestamp': datetime.now().isoformat()})
    if len(state['context_usage'][session_id]['entries']) > 100: state['context_usage'][session_id]['entries'] = state['context_usage'][session_id]['entries'][-100:]
    save_state(state)
    return {'status': 'success', 'session_totals': {'tokens_used': state['context_usage'][session_id]['total_tokens_used'], 'tokens_saved': state['context_usage'][session_id]['total_tokens_saved']}}

def prepare_handoff(session_id, target_agent, task_description, query_plan=None, file_ids=None, context_budget_tokens=None):
    state = load_state()
    session = state.get('sessions', {}).get(session_id, {})
    files_for_handoff = []
    if file_ids:
        for fid in file_ids:
            if fid in state.get('files', {}): files_for_handoff.append({'file_id': fid, 'managed_path': state['files'][fid]['managed_path']})
    if context_budget_tokens is None:
        budgets = {'sub_agent_large': 50000, 'sub_agent_standard': 15000, 'big_context_handler': 80000, 'creative_innovate': 20000}
        context_budget_tokens = budgets.get(target_agent, 20000)
    handoff_id = generate_id('handoff_')
    handoff_package = {'handoff_id': handoff_id, 'created_at': datetime.now().isoformat(), 'source_session_id': session_id, 'target_agent': target_agent, 'task_description': task_description, 'query_plan': query_plan, 'context_budget_tokens': context_budget_tokens, 'files': files_for_handoff, 'session_context': {'account_context': session.get('account_context', {}), 'current_goal': session.get('current_goal')}, 'status': 'prepared'}
    state['handoffs'][handoff_id] = handoff_package
    state['metrics']['total_handoffs'] += 1
    save_state(state)
    return {'status': 'success', 'handoff_id': handoff_id, 'package': handoff_package}

def init_session(session_name=None, account_context=None, auto_detect=True):
    state = load_state()
    if 'session_names' not in state: state['session_names'] = {}
    if session_name:
        normalized = normalize_name(session_name)
        if normalized in state['session_names']:
            session_id = state['session_names'][normalized]
            if session_id in state['sessions']:
                session = state['sessions'][session_id]
                session['last_accessed'] = datetime.now().isoformat()
                save_state(state)
                return {'status': 'resumed', 'session_id': session_id, 'session': session}
    new_session_id = generate_id('sess_')
    display_name = session_name or f"Session {datetime.now().strftime('%b %d %H:%M')}"
    state['sessions'][new_session_id] = {'id': new_session_id, 'name': display_name, 'created_at': datetime.now().isoformat(), 'last_accessed': datetime.now().isoformat(), 'account_context': account_context or {}, 'checkpoints': [], 'current_goal': None, 'key_facts': []}
    if session_name: state['session_names'][normalize_name(session_name)] = new_session_id
    save_state(state)
    return {'status': 'created', 'session_id': new_session_id, 'session_name': display_name}

def search_files(query, session_id=None):
    state = load_state()
    query_lower = query.lower()
    matches = []
    for fid, finfo in state.get('files', {}).items():
        if session_id and finfo.get('session_id') != session_id: continue
        if datetime.fromisoformat(finfo['expires_at']) < datetime.now(): continue
        score = 0; match_reasons = []
        search_idx = finfo.get('search_index', {})
        for name in search_idx.get('campaign_names', []):
            if query_lower in name.lower(): score += 15; match_reasons.append(f"campaign: {name}")
        for name in search_idx.get('entity_names', []):
            if query_lower in name.lower(): score += 10; match_reasons.append(f"entity: {name}")
        if score > 0: matches.append({'file_id': fid, 'score': score, 'match_reasons': match_reasons[:5], 'managed_path': finfo.get('managed_path')})
    matches.sort(key=lambda x: x['score'], reverse=True)
    return {'status': 'success', 'query': query, 'count': len(matches), 'files': matches[:20]}

def run(action, **kwargs):
    actions_map = {
        'init_session': lambda: init_session(kwargs.get('session_name'), kwargs.get('account_context'), kwargs.get('auto_detect', True)),
        'cache_query_plan': lambda: cache_query_plan(kwargs['session_id'], kwargs['plan_name'], kwargs['query_plan'], kwargs.get('ttl_hours', DEFAULT_PLAN_TTL_HOURS)),
        'get_cached_plan': lambda: get_cached_plan(kwargs['session_id'], kwargs['plan_name']),
        'sync_sub_agent_state': lambda: sync_sub_agent_state(kwargs['handoff_id'], kwargs['sub_agent_id'], kwargs.get('status', 'started'), kwargs.get('current_step'), kwargs.get('progress_percent', 0)),
        'receive_sub_agent_result': lambda: receive_sub_agent_result(kwargs['handoff_id'], kwargs['result_summary'], kwargs.get('file_id'), kwargs.get('tokens_used', 0), kwargs.get('error')),
        'track_context_usage': lambda: track_context_usage(kwargs['session_id'], kwargs['agent_type'], kwargs['action'], kwargs['tokens_used'], kwargs.get('tokens_saved', 0)),
        'prepare_handoff': lambda: prepare_handoff(kwargs['session_id'], kwargs['target_agent'], kwargs['task_description'], kwargs.get('query_plan'), kwargs.get('file_ids'), kwargs.get('context_budget_tokens')),
        'search_files': lambda: search_files(kwargs['query'], kwargs.get('session_id')),
        'get_metrics': lambda: {'status': 'success', 'metrics': load_state().get('metrics', {})}
    }
    if action not in actions_map: return {'status': 'error', 'message': f'Unknown action: {action}', 'available_actions': list(actions_map.keys())}
    try: return actions_map[action]()
    except KeyError as e: return {'status': 'error', 'message': f'Missing required parameter: {e}'}
    except Exception as e: return {'status': 'error', 'message': str(e)}
