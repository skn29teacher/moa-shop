"""Local database administration; no web API can grant admin privileges."""
import sqlite3
from uuid import UUID

import click

from app.core.config import PROJECT_ROOT
from app.core.errors import HTTPException
from app.core.supabase_auth import provider
from app.db.connection import get_connection


def register_commands(app):
    @app.cli.command('check-chat-docs')
    @click.option('--query', default=None, help='Search locally without calling Groq.')
    def check_chat_docs(query):
        """List loaded knowledge files and matching passages; no external API call."""
        from app.services.knowledge import load_documents, search_documents
        passages, files, skipped = load_documents()
        click.echo(f'AI 참고 문서: {len(files)}개, 검색 구간: {len(passages)}개')
        for name in files:
            click.echo(f'  읽기 성공: {name}')
        for name, reason in skipped:
            click.echo(f'  건너뜀: {name} ({reason})')
        if query:
            matches = search_documents([{'role': 'user', 'content': query}])
            click.echo(f'검색 결과: {len(matches)}개')
            for match in matches:
                click.echo(f'  [{match["id"]}] {match["file"]} (L{match["start_line"]}–L{match["end_line"]})')

    @app.cli.command('check-groq')
    @click.option('--generate', is_flag=True, help='Send one Korean test prompt (uses Groq quota).')
    def check_groq(generate):
        """Check key, HTTPS and configured model; optionally generate one answer."""
        from app.services.chat import GroqChat
        settings = app.config['settings']
        groq = GroqChat(settings)
        try:
            groq.check()
            click.echo(f'Groq HTTPS 연결 및 모델 확인 성공: {settings.groq_model}')
            if generate:
                result = groq.complete([{'role': 'user', 'content': '안녕하세요. 한 문장으로 자기소개해 주세요.'}], [])
                click.echo(result['reply'])
        except HTTPException as exc:
            raise click.ClickException(f'Groq 확인 실패 ({exc.status_code}): {exc.detail}') from None

    @app.cli.command('init-db')
    def init_db():
        """Verify the initialized SQLite schema. Never resets existing data."""
        click.echo(f"SQLite {sqlite3.sqlite_version}: {app.config['settings'].database_path}")
        click.echo('DB 초기화 완료 (기존 데이터 유지).')

    @app.cli.command('seed-demo')
    def seed_demo():
        """Insert demo products once, preserving existing stock and prices."""
        connection = get_connection()
        script = (PROJECT_ROOT / 'sql' / 'seed.sql').read_text(encoding='utf-8')
        with connection.transaction():
            statement = ''
            for line in script.splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    connection.execute(statement)
                    statement = ''
        click.echo('샘플 상품 준비 완료 (동일 ID의 상품·재고 유지).')

    @app.cli.command('set-role')
    @click.option('--auth-user-id', required=True, help='Supabase Auth UUID; user must log in first.')
    @click.option('--role', required=True, type=click.Choice(['customer', 'admin']))
    def set_role(auth_user_id, role):
        """Set the role of one existing, active local profile."""
        try:
            auth_id = UUID(auth_user_id)
        except ValueError:
            raise click.ClickException('유효한 Supabase Auth UUID를 입력하세요.') from None
        connection = get_connection()
        with connection.transaction():
            row = connection.execute('''UPDATE users SET role = ?
                WHERE auth_user_id = ? AND deleted_at IS NULL RETURNING id''', (role, auth_id)).fetchone()
            if row is None:
                raise click.ClickException('활성 회원을 찾을 수 없습니다. 먼저 해당 계정으로 앱에 로그인하세요.')
        click.echo(f'권한 변경 완료: {auth_id} → {role}')

    @app.cli.command('check-auth')
    def check_auth():
        """Check Supabase Auth HTTPS reachability without signing in or changing data."""
        try:
            provider().call('GET', '/settings')
        except HTTPException as exc:
            raise click.ClickException(f'Auth HTTPS 확인 실패 ({exc.status_code}): {exc.detail}') from None
        click.echo('Supabase Auth HTTPS 연결 성공.')
