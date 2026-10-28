from pathlib import Path

from django.conf import settings
from django.utils import timezone

from ..models import Document, IndexingJob


def is_within_approved_root(path) -> bool:
    try:
        p = Path(path).resolve()
    except Exception:
        return False
    for root in settings.APPROVED_FOLDER_ROOTS:
        try:
            r = Path(root).resolve()
            p.relative_to(r)
            return True
        except Exception:
            continue
    return False


def safe_walk(root, extensions, max_size_mb):
    root = Path(root).resolve()
    allowed_exts = {e.strip().lower() for e in extensions if e.strip()}
    max_bytes = max_size_mb * 1024 * 1024

    for path in root.rglob("*"):
        try:
            if path.is_symlink():
                continue
            if not path.is_file():
                continue
            if path.suffix.lower() not in allowed_exts:
                continue
            if path.stat().st_size > max_bytes:
                continue
            yield path
        except OSError:
            continue


def run_indexing(job: IndexingJob, index_document_fn):
    source = job.folder_source
    job.status = IndexingJob.STATUS_RUNNING
    job.save(update_fields=["status"])

    root = Path(source.root_path).resolve()
    if not is_within_approved_root(root):
        job.status = IndexingJob.STATUS_FAILED
        job.message = "Root path is not within an approved folder root."
        job.finished_at = timezone.now()
        job.save()
        return

    extensions = [e for e in source.extensions.split(",") if e.strip()]
    files = list(safe_walk(root, extensions, source.max_size_mb))
    job.files_total = len(files)
    job.save(update_fields=["files_total"])

    for path in files:
        doc = None
        try:
            rel = str(path.relative_to(root))
            doc, _ = Document.objects.update_or_create(
                folder_source=source,
                source_path=str(path),
                defaults={
                    "title": rel,
                    "file_type": path.suffix.lower().lstrip("."),
                    "status": Document.STATUS_PROCESSING,
                    "size": path.stat().st_size,
                    "owner": None,
                },
            )
            index_document_fn(doc)
            doc.status = Document.STATUS_READY
            doc.error = ""
            doc.save(update_fields=["status", "error"])
            job.files_indexed += 1
        except Exception as exc:  # noqa: BLE001
            job.files_failed += 1
            if doc is not None:
                doc.status = Document.STATUS_FAILED
                doc.error = str(exc)[:500]
                doc.save(update_fields=["status", "error"])
        job.save(update_fields=["files_indexed", "files_failed"])

    job.status = IndexingJob.STATUS_DONE
    job.finished_at = timezone.now()
    job.save()