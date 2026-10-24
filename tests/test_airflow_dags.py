"""Queue tests run anywhere; DAG tests additionally run inside Airflow Docker."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

from source.orchestration.airflow_batches import (
    QueueConfig, digest_file, process_queue, save_json, submit_batch,
)


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.config = QueueConfig(self.root, sys.executable, 'test', 'http://qdrant:6333')
        self.csv = self.root / 'source.csv'
        self.csv.write_text('product_id,content,rating\n1,tốt,5\n', encoding='utf-8')

    def tearDown(self):
        self.directory.cleanup()

    def test_submit_atomic_and_duplicate_content(self):
        first = submit_batch(self.csv, self.root)
        self.assertEqual(first, submit_batch(self.csv, self.root))
        self.assertEqual(first.stem, digest_file(first))
        self.assertEqual(len(list(first.parent.glob('*.csv'))), 1)
        self.csv.write_text('content\ntext\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            submit_batch(self.csv, self.root)

    def test_success_receipt_archive_and_no_double_processing(self):
        submit_batch(self.csv, self.root)
        executor = Mock(return_value={'completed_at': 'now', 'batch_id': 'abc', 'new_reviews': 1})
        result = process_queue(self.config, executor)
        self.assertEqual(result['completed_batches'], 1)
        submitted_path = executor.call_args.args[1]
        self.assertEqual(submitted_path.parent.name, 'processing')
        self.assertEqual(len(list((self.config.queue / 'archive').glob('*.csv'))), 1)
        submit_batch(self.csv, self.root)
        self.assertEqual(process_queue(self.config, executor)['completed_batches'], 0)
        self.assertEqual(executor.call_count, 1)

    def test_failure_retries_processing_before_new_inbox(self):
        submit_batch(self.csv, self.root)
        executor = Mock(side_effect=RuntimeError('worker failed'))
        with self.assertRaises(RuntimeError):
            process_queue(self.config, executor)
        self.assertFalse(list((self.config.queue / 'receipts').glob('*.json')))
        original_working = executor.call_args.args[1]
        executor.side_effect = None
        executor.return_value = {'completed_at': 'now', 'batch_id': 'abc'}
        self.assertEqual(process_queue(self.config, executor)['completed_batches'], 1)
        self.assertEqual(executor.call_args.args[1], original_working)

    def test_foreign_pending_is_rejected(self):
        pending = self.root / 'data/processed/kb_batches/pending.json'
        save_json(pending, {'input': 'C:\\old\\missing.csv', 'identity': {}})
        executor = Mock()
        with self.assertRaisesRegex(RuntimeError, 'original environment'):
            process_queue(self.config, executor)
        executor.assert_not_called()

    def test_pending_original_path_and_config_are_preserved(self):
        pending = self.root / 'data/processed/kb_batches/pending.json'
        save_json(pending, {'input': str(self.csv), 'identity': {
            'url': self.config.url, 'collection': 'test', 'model': 'logreg', 'revision': '1'}})
        def execute(config, path):
            self.assertEqual(path, self.csv)
            pending.unlink()
            return {'completed_at': 'now', 'batch_id': 'abc'}
        self.assertEqual(process_queue(self.config, execute)['completed_batches'], 1)

    def test_batch_limit(self):
        submit_batch(self.csv, self.root)
        self.csv.write_text('product_id,content,rating\n2,khác,4\n', encoding='utf-8')
        submit_batch(self.csv, self.root)
        config = QueueConfig(self.root, sys.executable, 'test', self.config.url, max_batches=1)
        executor = Mock(return_value={'completed_at': 'now'})
        self.assertEqual(process_queue(config, executor)['completed_batches'], 1)
        self.assertEqual(executor.call_count, 1)


try:
    AIRFLOW_AVAILABLE = importlib.util.find_spec('airflow.sdk') is not None
except ModuleNotFoundError:
    AIRFLOW_AVAILABLE = False


@unittest.skipUnless(AIRFLOW_AVAILABLE, 'Run DAG tests in the Airflow container')
class DagTests(unittest.TestCase):
    def test_dag_import_and_single_writer_settings(self):
        from airflow.dag_processing.dagbag import DagBag
        folder = Path(os.getenv('AIRFLOW__CORE__DAGS_FOLDER', '/opt/airflow/dags'))
        self.assertTrue((folder / 'kb_incremental_dag.py').is_file())
        bag = DagBag(dag_folder=str(folder), safe_mode=False)
        self.assertEqual(bag.import_errors, {})
        dag = bag.dags['tiki_kb_incremental']
        self.assertEqual(dag.max_active_runs, 1)
        self.assertEqual(dag.max_active_tasks, 1)
        self.assertFalse(dag.catchup)
        self.assertEqual(set(dag.task_ids), {'process_batches', 'report'})
        self.assertEqual(dag.get_task('process_batches').retries, 2)
        self.assertGreater(dag.get_task('process_batches').execution_timeout.total_seconds(), 0)


if __name__ == '__main__':
    unittest.main()
