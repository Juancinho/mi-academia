import json
from copy import deepcopy
from pathlib import Path
import os
import subprocess
import sys

import pytest

from academia.vault_sync import build_files, choose_area, digest, safe_target, slug, sync_snapshot


@pytest.fixture
def snapshot():
    return {
        'format': 'mi-academia-vault', 'version': 1,
        'notebooks': [{'id': 'b1', 'title': 'Lógica', 'version': 1, 'summary': 'Reglas y evidencia', 'knowledge': [{'id': 'local', 'topics': ['Lógica']}],
                       'concepts': [{'id': 'k1', 'title': 'Inferencia'}], 'sources': [{'id': 's1', 'title': 'Conversación', 'kind': 'chatgpt', 'citation': 'Origen aportado'}],
                       'conversation_ids': ['c1'], 'notes': {'objectives': ['Razonar'], 'sections': [{'title': 'Regla', 'body': '$P \\Rightarrow Q$\n\n```mermaid\nflowchart LR\n A-->B\n```', 'source_ids': ['s1']}], 'glossary': [], 'open_questions': []}}],
        'knowledge': [{'id': 'k1', 'title': 'Inferencia', 'content': 'P implica Q', 'topics': ['Lógica'], 'epistemic': 'verificable', 'stage': 'Registrado', 'evidence': [{'session_id': 'b1', 'session_title': 'Lógica', 'locator': 'Turno 1', 'excerpt': 'P implica Q'}]}],
        'relations': [], 'conversations': [{'id': 'c1', 'title': 'Aprender lógica', 'coverage': 'extracts', 'messages': [{'role': 'material', 'text': 'Fragmento'}]}],
        'conversation_sessions': [{'conversation_id': 'c1', 'session_id': 'b1'}]
    }


def test_vault_contains_subfolders_backlinks_math_diagrams_and_origin(snapshot, tmp_path):
    result = sync_snapshot(snapshot, tmp_path)
    assert result['written'] == 7
    root = tmp_path / 'Mi Academia'
    for folder in ['00 Inicio', '01 Temas', '02 Fuentes']:
        assert (root / folder).is_dir()
    area = root / '01 Temas' / 'Ciencias y matemáticas'
    assert {p.name for p in area.iterdir() if p.is_dir()} == {'Cuadernos', 'Conceptos', 'Conversaciones', 'Mapas'}
    notebook = next((area / 'Cuadernos').glob('*.md')).read_text(encoding='utf-8')
    assert '```mermaid' in notebook and '$P' in notebook
    assert '/Conceptos/' in notebook and '/Conversaciones/' in notebook
    chat = next((area / 'Conversaciones').glob('*.md')).read_text(encoding='utf-8')
    assert 'no es el chat completo' in chat
    assert sync_snapshot(snapshot, tmp_path) == {'written': 0, 'unchanged': 7, 'conflicts': 0}


def test_local_edits_are_preserved_and_remote_conflict_becomes_a_copy(snapshot, tmp_path):
    sync_snapshot(snapshot, tmp_path)
    notebook = next((tmp_path / 'Mi Academia' / '01 Temas').glob('*/Cuadernos/*.md'))
    notebook.write_text('Mis anotaciones personales', encoding='utf-8')
    assert sync_snapshot(snapshot, tmp_path)['conflicts'] == 0
    snapshot['notebooks'][0]['notes']['sections'][0]['body'] = 'Desarrollo nuevo en la nube'
    result = sync_snapshot(snapshot, tmp_path)
    assert result['conflicts'] == 1
    assert notebook.read_text(encoding='utf-8') == 'Mis anotaciones personales'
    assert len(list(notebook.parent.glob('*.nube-*.md'))) == 1
    assert sync_snapshot(snapshot, tmp_path)['conflicts'] == 0


def test_titles_and_topic_changes_keep_existing_link_paths(snapshot, tmp_path):
    sync_snapshot(snapshot, tmp_path)
    manifest = json.loads((tmp_path / 'Mi Academia' / '.sync-state.json').read_text(encoding='utf-8'))
    snapshot['notebooks'][0]['title'] = 'Otro nombre'
    files = build_files(snapshot, manifest)
    assert files['book:b1'][0] == manifest['book:b1']['path']
    assert 'Otro nombre' in files['book:b1'][1]


def test_sync_never_deletes_or_touches_other_vault_files(snapshot, tmp_path):
    personal = tmp_path / 'Mi diario.md'
    personal.write_text('Personal', encoding='utf-8')
    sync_snapshot(snapshot, tmp_path)
    original = list((tmp_path / 'Mi Academia').rglob('*.md'))
    snapshot['notebooks'] = []
    snapshot['knowledge'] = []
    snapshot['conversations'] = []
    sync_snapshot(snapshot, tmp_path)
    assert personal.read_text(encoding='utf-8') == 'Personal'
    assert all(path.exists() for path in original)


def test_sync_rejects_bad_responses_and_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        sync_snapshot({'format': 'html-login-page'}, tmp_path)
    for path in ['../otro.md', str(tmp_path.parent / 'outside.md')]:
        with pytest.raises(ValueError):
            safe_target(tmp_path, path)
    assert '/' not in slug('../../CON: [x]')
    assert slug('CON') == '_CON'


def test_configured_runner_writes_only_a_summary_log(snapshot, tmp_path):
    vault = tmp_path / 'vault'
    vault.mkdir()
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'vault': str(vault)}), encoding='utf-8')
    source = tmp_path / 'snapshot.json'
    source.write_text(json.dumps(snapshot), encoding='utf-8')
    result = subprocess.run([sys.executable, '-m', 'academia.vault_sync', '--config', str(config), '--snapshot', str(source)], capture_output=True, text=True)
    assert result.returncode == 0
    report = json.loads(config.with_name('last-result.json').read_text(encoding='utf-8'))
    assert report == {'written': 7, 'unchanged': 0, 'conflicts': 0}
    assert 'Fragmento' not in config.with_name('last-result.json').read_text(encoding='utf-8')


def test_runner_failure_never_logs_note_bodies_or_credentials(tmp_path):
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'vault': str(tmp_path / 'absent')}), encoding='utf-8')
    result = subprocess.run([sys.executable, '-m', 'academia.vault_sync', '--config', str(config)], capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads(config.with_name('last-result.json').read_text(encoding='utf-8'))
    assert set(report) == {'error', 'message'}


@pytest.mark.skipif(os.name != 'nt', reason='Windows DPAPI')
def test_dpapi_restores_a_secret_without_persisting_plaintext():
    from academia.windows_secret import transform
    plaintext = b'non-sensitive-test-credential'
    protected = transform(plaintext)
    assert plaintext not in protected
    assert transform(protected, decrypt=True) == plaintext


def test_broad_areas_use_all_topics_and_allow_custom_assignment(snapshot):
    assert choose_area(['Medición', 'SCADA', 'electricidad']) == 'Energía e ingeniería'
    assert choose_area(['Fiscalidad', 'Economía']) == 'Economía y finanzas'
    assert choose_area(['CoWoS e integración 2.5D', 'HBM y la pared de memoria']) == 'Tecnología e informática'
    assert choose_area(['tema desconocido']) == 'Por organizar'
    assert choose_area(['FISCALIDAD'], organization={'topic_areas': {'fiscalidad': 'Sociedad'}}) == 'Sociedad'
    files = build_files(snapshot, {}, {'notebook_areas': {'b1': 'Mi área'}, 'topic_areas': {'Lógica': 'Mi área'}})
    assert all('/Mi área/' in files[k][0] for k in ['book:b1', 'concept:k1', 'chat:c1', 'topic:Lógica'])
    # Many fine topics become map files, never extra subfolders.
    snapshot['knowledge'][0]['topics'] = [f'tema {i}' for i in range(80)]
    paths = [path for path, _ in build_files(snapshot, {}).values()]
    assert len({str(Path(p).parent) for p in paths}) <= 7


def test_reorganization_moves_managed_notes_preserves_local_edits_and_fixes_links(snapshot, tmp_path):
    root = tmp_path / 'Mi Academia'
    root.mkdir()
    legacy = {}
    for key, (path, body) in build_files(snapshot, {}).items():
        path = '01 Cuadernos/Lógica/' + Path(path).name if key == 'book:b1' else '05 Mapas/' + Path(path).name
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding='utf-8')
        legacy[key] = {'path': path, 'hash': digest(body), 'remote_hash': digest(body)}
    old_book = root / legacy['book:b1']['path']
    old_book.write_text('Mis comentarios personales', encoding='utf-8')
    (root / '.sync-state.json').write_text(json.dumps(legacy), encoding='utf-8')
    report = sync_snapshot(snapshot, tmp_path)
    manifest = json.loads((root / '.sync-state.json').read_text(encoding='utf-8'))
    new_book = root / manifest['book:b1']['path']
    assert new_book.read_text(encoding='utf-8') == 'Mis comentarios personales'
    assert not old_book.exists() and not (root / '01 Cuadernos').exists()
    concept = root / manifest['concept:k1']['path']
    assert '[[Mi Academia/01 Temas/Ciencias y matemáticas/Cuadernos/' in concept.read_text(encoding='utf-8')
    assert report['conflicts'] == 0  # No upstream change to edited content.
    assert sync_snapshot(snapshot, tmp_path)['written'] == 0


def test_reorganization_never_overwrites_an_occupied_destination(snapshot, tmp_path):
    root = tmp_path / 'Mi Academia'
    root.mkdir()
    files = build_files(snapshot, {})
    relative, body = files['book:b1']
    old = 'legacy/' + Path(relative).name
    source = root / old
    source.parent.mkdir()
    source.write_text(body, encoding='utf-8')
    destination = root / relative
    destination.parent.mkdir(parents=True)
    destination.write_text('Nota ajena', encoding='utf-8')
    (root / '.sync-state.json').write_text(json.dumps({'book:b1': {'path': old, 'hash': digest(body)}}), encoding='utf-8')
    with pytest.raises(ValueError, match='ocupado'):
        sync_snapshot(snapshot, tmp_path)
    assert source.exists() and destination.read_text(encoding='utf-8') == 'Nota ajena'
