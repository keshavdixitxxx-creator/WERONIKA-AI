"""Checks for the opt-in call audio installer.

The installer must never be destructive or sneaky: a model archive is rejected unless it
has exactly one root folder and no path that escapes it, and a failed download leaves the
packages that did install in place instead of half-configuring the worker.
"""

import io
import subprocess
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import setup_calls
from setup_calls import (
    SetupError,
    base_name,
    best_engine,
    build_parser,
    extract_archive,
    install_vosk_model,
    main,
    missing_packages,
    plan_packages,
    summarise,
    vosk_model_present,
    vosk_model_root,
)


class FakeImportlib:
    """Stands in for importlib so a test can say which packages are installed."""

    def __init__(self, installed=()):
        self.installed = set(installed)

    @property
    def util(self):
        return self

    def find_spec(self, name):
        return object() if name in self.installed else None


def names(plan):
    return [base_name(name) for name, _reason in plan]


class PlanTests(unittest.TestCase):
    def test_the_default_plan_installs_both_engines_and_the_audio_and_voice_pieces(self):
        self.assertEqual(
            names(plan_packages()),
            ["sounddevice", "faster-whisper", "vosk", "pyttsx3"],
        )

    def test_choosing_one_engine_leaves_the_other_out(self):
        self.assertEqual(names(plan_packages(("whisper",))), ["sounddevice", "faster-whisper", "pyttsx3"])
        self.assertEqual(names(plan_packages(("vosk",))), ["sounddevice", "vosk", "pyttsx3"])

    def test_the_audio_and_voice_packages_can_be_skipped(self):
        self.assertNotIn("sounddevice", names(plan_packages(with_audio=False)))
        self.assertNotIn("pyttsx3", names(plan_packages(with_voice=False)))
        self.assertEqual(names(plan_packages(("vosk",), with_audio=False, with_voice=False)), ["vosk"])

    def test_every_planned_package_says_why_it_is_wanted(self):
        for _pip_name, reason in plan_packages():
            self.assertTrue(len(reason) > 20, reason)

    def test_a_version_specifier_is_stripped_before_any_comparison(self):
        self.assertEqual(base_name("faster-whisper>=1.0"), "faster-whisper")
        self.assertEqual(base_name("vosk>=0.3.45"), "vosk")
        self.assertEqual(base_name("sounddevice"), "sounddevice")


class EngineChoiceTests(unittest.TestCase):
    def test_whisper_wins_when_it_installed(self):
        self.assertEqual(best_engine(["sounddevice", "faster-whisper", "vosk"], []), "whisper")

    def test_vosk_is_the_engine_when_whisper_failed(self):
        self.assertEqual(best_engine(["sounddevice", "faster-whisper", "vosk"], ["faster-whisper"]), "vosk")

    def test_typed_mode_is_the_answer_when_no_engine_installed(self):
        self.assertEqual(best_engine(["sounddevice", "pyttsx3"], []), "typed")
        self.assertEqual(best_engine([], []), "typed")

    def test_versions_do_not_confuse_the_choice(self):
        self.assertEqual(best_engine(["faster-whisper>=1.0"], ["faster-whisper>=1.0"]), "typed")


class MissingPackageTests(unittest.TestCase):
    def test_a_package_that_imports_is_not_listed_as_missing(self):
        plan = plan_packages()
        with mock.patch.object(setup_calls, "importlib", FakeImportlib(["sounddevice", "vosk"])):
            self.assertEqual(missing_packages(plan), ["faster-whisper>=1.0", "pyttsx3>=2.90"])

    def test_nothing_is_missing_when_everything_is_installed(self):
        with mock.patch.object(
            setup_calls, "importlib",
            FakeImportlib(["sounddevice", "faster_whisper", "vosk", "pyttsx3"]),
        ):
            self.assertEqual(missing_packages(plan_packages()), [])

    def test_a_package_that_cannot_be_inspected_counts_as_missing(self):
        broken = FakeImportlib()
        broken.find_spec = mock.Mock(side_effect=ImportError("nope"))
        with mock.patch.object(setup_calls, "importlib", broken):
            self.assertEqual(missing_packages([("vosk>=0.3.45", "x")]), ["vosk>=0.3.45"])


class ArchiveSafetyTests(unittest.TestCase):
    def make_zip(self, entries):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        archive = Path(temp.name) / "model.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            for name, body in entries:
                zipped.writestr(name, body)
        return archive

    def test_a_normal_model_archive_extracts_into_its_own_folder(self):
        archive = self.make_zip([
            ("vosk-model-small-en-us-0.15/README", "read me"),
            ("vosk-model-small-en-us-0.15/am/final.mdl", "weights"),
        ])
        with TemporaryDirectory() as target:
            root = extract_archive(archive, Path(target))
            self.assertEqual(root.name, "vosk-model-small-en-us-0.15")
            self.assertTrue((root / "am" / "final.mdl").is_file())
            self.assertEqual((root / "README").read_text(), "read me")

    def test_an_archive_that_reaches_outside_its_folder_is_rejected(self):
        archive = self.make_zip([("model/../../evil.sh", "rm -rf /")])
        with TemporaryDirectory() as staging:
            target = Path(staging) / "out"
            with self.assertRaises(SetupError) as caught:
                extract_archive(archive, target)
            self.assertIn("unsafe path", str(caught.exception))
            self.assertFalse(target.exists(), "a rejected archive must not create its folder")

    def test_an_absolute_path_in_an_archive_is_rejected(self):
        archive = self.make_zip([("/etc/passwd", "x")])
        with TemporaryDirectory() as staging:
            target = Path(staging) / "out"
            with self.assertRaises(SetupError):
                extract_archive(archive, target)
            self.assertFalse(target.exists())

    def test_an_archive_with_two_roots_is_rejected(self):
        archive = self.make_zip([("one/file", "x"), ("two/file", "y")])
        with TemporaryDirectory() as staging:
            target = Path(staging) / "out"
            with self.assertRaises(SetupError) as caught:
                extract_archive(archive, target)
            self.assertIn("unexpected layout", str(caught.exception))
            self.assertFalse(target.exists())


class VoskModelTests(unittest.TestCase):
    def test_no_model_folder_means_no_model(self):
        with TemporaryDirectory() as temp, mock.patch.object(setup_calls, "MODEL_ROOT", Path(temp)):
            self.assertFalse(vosk_model_present())
            self.assertEqual(vosk_model_root(), Path(temp) / "vosk")

    def test_a_model_folder_is_found(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "vosk" / "vosk-model-small-en-us-0.15"
            root.mkdir(parents=True)
            with mock.patch.object(setup_calls, "MODEL_ROOT", Path(temp)):
                self.assertTrue(vosk_model_present())

    def test_an_existing_model_is_not_downloaded_again(self):
        with TemporaryDirectory() as temp:
            (Path(temp) / "vosk" / "vosk-model-small-en-us-0.15").mkdir(parents=True)
            with mock.patch.object(setup_calls, "MODEL_ROOT", Path(temp)), \
                    mock.patch.object(setup_calls, "download_zip", side_effect=AssertionError("downloaded")):
                note = install_vosk_model()
        self.assertIn("already present", note)

    def test_a_downloaded_model_lands_in_the_model_root(self):
        with TemporaryDirectory() as temp, TemporaryDirectory() as staging:
            archive = Path(staging) / "download.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("vosk-model-small-en-us-0.15/README", "read me")

            def fake_download(url, destination, limit=setup_calls.DOWNLOAD_LIMIT_BYTES):
                destination.mkdir(parents=True, exist_ok=True)
                copy = destination / "download.zip"
                copy.write_bytes(archive.read_bytes())
                return copy

            with mock.patch.object(setup_calls, "MODEL_ROOT", Path(temp)), \
                    mock.patch.object(setup_calls, "download_zip", side_effect=fake_download):
                note = install_vosk_model()
                self.assertTrue(vosk_model_present())
            self.assertIn(str(Path(temp) / "vosk" / "vosk-model-small-en-us-0.15"), note)

    def test_a_failed_download_does_not_pretend_the_model_is_there(self):
        with TemporaryDirectory() as temp:
            with mock.patch.object(setup_calls, "MODEL_ROOT", Path(temp)), \
                    mock.patch.object(setup_calls, "download_zip", side_effect=SetupError("offline")):
                with self.assertRaises(SetupError):
                    install_vosk_model()
            self.assertFalse(vosk_model_present())


class SummaryTests(unittest.TestCase):
    def test_a_complete_install_reports_the_engine_it_will_use(self):
        with mock.patch.object(setup_calls, "importlib", FakeImportlib(
                ["sounddevice", "faster_whisper", "vosk", "pyttsx3"])):
            report = summarise(plan_packages(), installed=["faster-whisper>=1.0"],
                               model_note="model ok", engine_choice="auto")
        self.assertEqual(report["engine"], "whisper")
        self.assertEqual(report["still_missing"], [])
        self.assertIn("Call audio is ready", str(report["message"]))
        self.assertIn("handle my calls", str(report["message"]))

    def test_an_install_that_added_nothing_reports_typed_mode(self):
        report = summarise(plan_packages(), installed=[], model_note="skipped", engine_choice="auto")
        self.assertEqual(report["engine"], "typed")
        self.assertEqual(len(report["still_missing"]), 4)
        self.assertIn("typed mode", str(report["message"]))
        self.assertIn("says she is an AI", str(report["message"]))

    def test_a_partial_install_names_what_is_still_missing(self):
        with mock.patch.object(setup_calls, "importlib", FakeImportlib(["sounddevice", "vosk"])):
            report = summarise(plan_packages(), installed=["vosk"], model_note="ok", engine_choice="vosk")
        self.assertEqual(report["engine"], "vosk")
        self.assertIn("faster-whisper>=1.0", report["still_missing"])
        self.assertIn("Part of the call audio support installed", str(report["message"]))
        self.assertIn("faster-whisper", str(report["message"]))

    def test_the_report_keeps_what_was_planned_and_installed(self):
        report = summarise(plan_packages(), installed=["vosk"], model_note="note", engine_choice="vosk")
        self.assertEqual(report["installed"], ["vosk"])
        self.assertEqual(report["engine_choice"], "vosk")
        self.assertEqual(report["model"], "note")


class CommandLineTests(unittest.TestCase):
    def test_the_flags_the_batch_file_passes_are_accepted(self):
        args = build_parser().parse_args(["--engines", "vosk", "--no-models", "--no-voice"])
        self.assertEqual(args.engines, "vosk")
        self.assertTrue(args.no_models)
        self.assertTrue(args.no_voice)
        self.assertFalse(args.report)

    def test_an_unknown_engine_is_refused(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["--engines", "dragon"])

    def test_report_mode_installs_nothing_and_exits_cleanly(self):
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("ran a command")), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as printed:
            self.assertEqual(main(["--report"]), 0)
        self.assertIn("Speech engines installed", printed.getvalue())

    def test_the_default_plan_is_everything_the_documentation_promises(self):
        self.assertEqual(
            {base_name(pip_name) for _import_name, pip_name, _reason in setup_calls.PACKAGES},
            {"sounddevice", "faster-whisper", "vosk", "pyttsx3"},
        )

    def test_every_package_documents_its_import_name_and_its_purpose(self):
        for import_name, pip_name, reason in setup_calls.PACKAGES:
            self.assertTrue(import_name and pip_name and reason)
            self.assertTrue(base_name(pip_name).replace("-", "_").startswith(import_name.split("_")[0]))


if __name__ == "__main__":
    unittest.main()
