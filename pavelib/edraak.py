"""
Edraak internationalization tasks
"""
from path import path
from paver.easy import task, needs, sh
import polib
from git import Repo
import os
from .utils.cmd import django_cmd

PLATFORM_ROOT = path('.')
git_repo = Repo(PLATFORM_ROOT)

try:
    from pygments.console import colorize
except ImportError:
    colorize = lambda color, text: text  # pylint: disable-msg=invalid-name


@task
def edraak_transifex_pull():
    # Start with clean translation state
    clean_git_repo_msg = 'The repo has local modifications. Please stash or commit your changes.'
    assert not git_repo.is_dirty(untracked_files=True), clean_git_repo_msg

    # Get Edraak translations
    for resource in ('edraak-platform', 'edraak-platform-2015-theme'):
        sh('tx pull --force --mode=reviewed --language=ar --resource=edraak.{}'.format(resource))


@task
def edraak_generate_files():
    """
    Append all Edraak strings to the original django.mo.
    """
    lc_messages_dir = PLATFORM_ROOT / 'conf/locale/ar/LC_MESSAGES'

    django_pofile_name = lc_messages_dir / 'django.po'
    django_mofile_name = lc_messages_dir / 'django.mo'

    django_pofile = polib.pofile(django_pofile_name)

    for resource in ('edraak-platform.po', 'edraak-platform-2015-theme.po'):
        edraak_pofile_name = lc_messages_dir / resource
        edraak_pofile = polib.pofile(edraak_pofile_name)

        for entry in edraak_pofile:
            django_pofile.append(entry)

    # Save a backup in git for later inspection, and keep django.po untouched
    customized_pofile_name = lc_messages_dir / 'django-edraak-customized.po'
    django_pofile.save(customized_pofile_name)
    django_pofile.save_as_mofile(django_mofile_name)


@task
@needs(
    'pavelib.edraak.edraak_transifex_pull',
    'pavelib.edraak.edraak_generate_files',
)
def edraak_i18n_pull():
    """
    Pulls Edraak-specific translation files.
    """
    files_to_add = (
        'conf/locale/ar/LC_MESSAGES/edraak-platform-2015-theme.po',
        'conf/locale/ar/LC_MESSAGES/edraak-platform.po',
        'conf/locale/ar/LC_MESSAGES/django.mo',
        'conf/locale/ar/LC_MESSAGES/django-edraak-customized.po',
    )

    sh('git add --force {}'.format(' '.join(files_to_add)))
    sh('git commit -m "Update Edraak translations (autogenerated message)" --edit')


@task
def edraak_i18n_theme_push():
    """
    Run theme's ./scripts/edraak_i18n_theme_push.sh.
    """
    sh(django_cmd('lms', 'devstack', 'edraak_i18n_theme_push'))

@task
@needs(
    'pavelib.edraak.edraak_i18n_theme_push',
    'pavelib.i18n.i18n_extract',
)
def edraak_i18n_push():
    """
    Extracts Edraak-specific translation strings and append it to the provided .PO file.

    It searches for translation strings that are marked
    with "# Translators: Edraak-specific" comment.
    """
    english_po_dir = PLATFORM_ROOT / 'conf/locale/en/LC_MESSAGES'

    edraak_specific_path = english_po_dir / 'edraak-platform.po'
    if edraak_specific_path.exists():
        edraak_specific_path.unlink()

    edraak_specific = polib.POFile()

    edraak_specific.metadata = {
        'Project-Id-Version': 'Edraak 1',
        'Report-Msgid-Bugs-To': 'dev@qrf.org',
        'POT-Creation-Date': '2014-12-15 11:17+0200',
        'PO-Revision-Date': 'YEAR-MO-DA HO:MI+ZONE',
        'Last-Translator': 'Edraak Dev <dev@qrf.org>',
        'Language-Team': 'Edraak Dev <dev@qrf.org>',
        'MIME-Version': '1.0',
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Transfer-Encoding': '8bit',
        'Generated-By': 'Paver',
    }

    for po_path in sorted(os.listdir(english_po_dir)):
        # Avoid .mo files
        if not po_path.endswith('.po'):
            continue

        if po_path == 'edraak-platform.po':
            continue

        pofile = polib.pofile(english_po_dir / po_path)

        for entry in pofile:
            if 'edraak-specific' in entry.comment.lower():
                edraak_specific.append(entry)

    edraak_specific.save(edraak_specific_path)

    sh('tx push -l en -s -r edraak.edraak-platform')
