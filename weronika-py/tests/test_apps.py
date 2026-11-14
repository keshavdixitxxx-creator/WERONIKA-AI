import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

from weronika_agent.apps import APP_ALIASES, AppError, AppLauncher, OpenService, clean_app_name
from weronika_agent.http_server import LocalServer, make_handler
from weronika_agent.site_service import SiteService
from weronika_agent.workflow import MessagingService
from weronika_agent.workspace import LocalWorkspace

WHATSAPP_ID = "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"


class FakeRunner:
    """Records what would have been started. Nothing really runs."""

    def __init__(self, installed_binaries=(), start_apps=None):
        self.spawned = []
        self.ran = []
        self.files = []
        self.captures = 0
        self.binaries = set(installed_binaries)
        self.start_apps = start_apps if start_apps is not None else []
        self.fail_capture = False

    def spawn(self, argv):
        self.spawned.append(list(argv))

    def run(self, argv, timeout=15.0):
        self.ran.append(list(argv))
        return 0

    def capture(self, argv, timeout=15.0):
        self.captures += 1
        if self.fail_capture:
            raise OSError("powershell is not available")
        return json.dumps(self.start_apps)

    def start_file(self, target):
        self.files.append(target)

    def which(self, name):
        return f"/usr/bin/{name}" if name in self.binaries else None

    @property
    def started(self):
        return len(self.spawned) + len(self.ran) + len(self.files)


class FakeBrowser:
    def __init__(self):
        self.urls = []

    def open_workspace_urls(self, urls):
        self.urls.extend(urls)
        return [{"id": f"t{index}", "url": url, "status": "opened"} for index, url in enumerate(urls)]

    def workspace_tabs(self):
        return []


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class WindowsCase(unittest.TestCase):
    shortcuts = (
        "Google Chrome",
        "Visual Studio Code",
        "Spotify",
        "Uninstall Spotify",
        "OBS Studio",
        "Android Studio",
        "Word",
    )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.menu = Path(self.temp.name) / "Programs"
        (self.menu / "Tools").mkdir(parents=True)
        for name in self.shortcuts:
            (self.menu / f"{name}.lnk").write_bytes(b"")
        (self.menu / "Tools" / "Blender.lnk").write_bytes(b"")
        self.runner = FakeRunner(start_apps=[{"Name": "WhatsApp", "AppID": WHATSAPP_ID}])
        self.clock = Clock()
        self.apps = AppLauncher(
            platform="win32", runner=self.runner, environ={}, app_dirs=[self.menu], clock=self.clock
        )

    def tearDown(self):
        self.temp.cleanup()

    def shortcut(self, name):
        return str(self.menu / f"{name}.lnk")


class WindowsLauncherTests(WindowsCase):
    def test_a_system_tool_starts_through_the_command_prompt(self):
        result = self.apps.open("notepad")
        self.assertEqual(self.runner.spawned, [["cmd", "/c", "start", "", "notepad"]])
        self.assertEqual(result["opened"], [{"name": "Notepad", "kind": "app"}])
        self.assertIn("Opened Notepad", result["message"])

    def test_filler_words_and_several_names(self):
        self.apps.open(["the calculator app", "my paint program"])
        self.assertEqual(
            self.runner.spawned,
            [["cmd", "/c", "start", "", "calc"], ["cmd", "/c", "start", "", "mspaint"]],
        )

    def test_settings_opens_through_its_system_address(self):
        self.apps.open("settings")
        self.assertEqual(self.runner.files, ["ms-settings:"])
        self.assertEqual(self.runner.spawned, [])

    def test_an_installed_program_opens_through_its_start_menu_shortcut(self):
        self.apps.open("chrome")
        self.apps.open("vs code")
        self.apps.open("blender")
        self.assertEqual(
            self.runner.files,
            [
                self.shortcut("Google Chrome"),
                self.shortcut("Visual Studio Code"),
                str(self.menu / "Tools" / "Blender.lnk"),
            ],
        )

    def test_a_store_app_opens_through_the_apps_folder(self):
        self.apps.open("whatsapp")
        self.assertEqual(self.runner.spawned, [["explorer.exe", f"shell:AppsFolder\\{WHATSAPP_ID}"]])

    def test_an_unknown_name_starts_nothing(self):
        with self.assertRaises(AppError) as raised:
            self.apps.open("flappy penguin")
        self.assertIn("could not find an app", str(raised.exception))
        self.assertEqual(self.runner.started, 0)

    def test_one_unknown_name_stops_the_whole_request(self):
        with self.assertRaises(AppError):
            self.apps.open(["notepad", "flappy penguin"])
        self.assertEqual(self.runner.started, 0)

    def test_command_text_is_never_run(self):
        for text in (
            'notepad" & del C:\\x',
            "notepad & calc",
            "notepad | calc",
            "$(calc)",
            "calc; shutdown /s",
            "..\\..\\Windows\\System32\\cmd.exe",
            "x" * 80,
        ):
            with self.assertRaises(AppError, msg=text):
                self.apps.open(text)
        self.assertEqual(self.runner.started, 0)

    def test_every_started_command_comes_from_the_fixed_table(self):
        for name in APP_ALIASES:
            try:
                self.apps.open(name)
            except AppError:
                continue
        for argv in self.runner.spawned:
            self.assertIn(argv[0], {"cmd", "explorer.exe"})
            if argv[0] == "cmd":
                self.assertEqual(argv[:4], ["cmd", "/c", "start", ""])
                self.assertRegex(argv[4], r"^[a-z]+$")
                self.assertEqual(len(argv), 5)

    def test_uninstallers_are_not_apps(self):
        self.apps.open("spotify")
        self.assertEqual(self.runner.files, [self.shortcut("Spotify")])
        with self.assertRaises(AppError):
            self.apps.open("uninstall spotify")

    def test_a_vague_name_is_not_guessed(self):
        with self.assertRaises(AppError) as raised:
            self.apps.open("studio")
        self.assertIn("Several apps match", str(raised.exception))
        self.assertIn("OBS Studio", str(raised.exception))
        self.assertEqual(self.runner.started, 0)

    def test_the_app_list_is_read_once_and_refreshed_later(self):
        self.apps.open("chrome")
        self.apps.open("whatsapp")
        self.assertEqual(self.runner.captures, 1)
        self.clock.now += 500
        self.apps.open("chrome")
        self.assertEqual(self.runner.captures, 2)

    def test_shortcuts_still_work_when_the_start_menu_query_fails(self):
        self.runner.fail_capture = True
        self.apps.open("chrome")
        self.assertEqual(self.runner.files, [self.shortcut("Google Chrome")])
        with self.assertRaises(AppError):
            self.apps.open("whatsapp")

    def test_clean_app_name(self):
        self.assertEqual(clean_app_name("  the Calculator app. "), "Calculator")
        self.assertEqual(clean_app_name("VS Code"), "VS Code")
        self.assertEqual(clean_app_name("a/b"), "")
        self.assertEqual(clean_app_name(""), "")


class MusicTests(WindowsCase):
    def test_spotify_app_shows_the_song(self):
        result = self.apps.music("spotify", "tum hi ho")
        self.assertEqual(self.runner.files, ["spotify:search:tum%20hi%20ho"])
        self.assertEqual(result["where"], "app")
        self.assertIn("Press play", result["message"])

    def test_the_song_name_cannot_leave_the_search_address(self):
        self.apps.music("Spotify", "x:y/z?a=b&c #d")
        self.assertEqual(self.runner.files, ["spotify:search:x%3Ay%2Fz%3Fa%3Db%26c%20%23d"])

    def test_without_the_app_the_web_player_opens_in_the_own_browser(self):
        (self.menu / "Spotify.lnk").unlink()
        opened = []
        result = self.apps.music("spotify", "tum hi ho", opened.append)
        self.assertEqual(opened, ["https://open.spotify.com/search/tum%20hi%20ho"])
        self.assertEqual(result["where"], "browser")
        self.assertEqual(self.runner.started, 0)

    def test_refusals(self):
        with self.assertRaises(AppError):
            self.apps.music("winamp", "tum hi ho")
        with self.assertRaises(AppError):
            self.apps.music("spotify", "   ")
        (self.menu / "Spotify.lnk").unlink()
        with self.assertRaises(AppError):
            self.apps.music("spotify", "tum hi ho")
        self.assertEqual(self.runner.started, 0)


class OtherSystemsTests(unittest.TestCase):
    def test_macos_uses_open(self):
        runner = FakeRunner()
        AppLauncher(platform="darwin", runner=runner, environ={}, app_dirs=[]).open("calculator")
        self.assertEqual(runner.ran, [["open", "-a", "Calculator"]])

    def test_linux_starts_the_first_installed_program(self):
        runner = FakeRunner(installed_binaries={"kcalc"})
        AppLauncher(platform="linux", runner=runner, environ={}, app_dirs=[]).open("calculator")
        self.assertEqual(runner.spawned, [["/usr/bin/kcalc"]])

    def test_linux_without_the_program_reports_it(self):
        runner = FakeRunner()
        with self.assertRaises(AppError):
            AppLauncher(platform="linux", runner=runner, environ={}, app_dirs=[]).open("calculator")
        self.assertEqual(runner.started, 0)

    def test_a_windows_only_tool_is_unknown_elsewhere(self):
        runner = FakeRunner()
        with self.assertRaises(AppError):
            AppLauncher(platform="linux", runner=runner, environ={}, app_dirs=[]).open("control panel")


class OpenServiceTests(WindowsCase):
    def setUp(self):
        super().setUp()
        self.browser = FakeBrowser()
        self.service = OpenService(SiteService(self.browser), self.apps)

    def test_apps_and_sites_in_one_request(self):
        result = self.service.open(["notepad", "youtube"])
        self.assertEqual(self.runner.spawned, [["cmd", "/c", "start", "", "notepad"]])
        self.assertEqual(self.browser.urls, ["https://www.youtube.com/"])
        self.assertEqual(
            sorted((entry["name"], entry["kind"]) for entry in result["opened"]),
            [("Notepad", "app"), ("YouTube", "site")],
        )
        self.assertIn("on this computer", result["message"])
        self.assertIn("Weronika browser window", result["message"])

    def test_calendar_means_google_calendar_unless_the_app_is_asked_for(self):
        self.service.open("calendar")
        self.assertEqual(self.browser.urls, ["https://calendar.google.com/"])
        self.assertEqual(self.runner.started, 0)
        self.service.open([{"name": "calendar", "kind": "app"}])
        self.assertEqual(self.runner.files, ["outlookcal:"])

    def test_an_installed_program_wins_over_its_website(self):
        self.service.open(["spotify", "word"])
        self.assertEqual(self.runner.files, [self.shortcut("Spotify"), self.shortcut("Word")])
        self.assertEqual(self.browser.urls, [])

    def test_the_website_opens_when_the_program_is_not_installed(self):
        (self.menu / "Spotify.lnk").unlink()
        self.service.open("spotify")
        self.assertEqual(self.browser.urls, ["https://open.spotify.com/"])
        self.assertEqual(self.runner.started, 0)

    def test_addresses_and_program_files(self):
        self.service.open(["github.com", "notepad.exe"])
        self.assertEqual(self.browser.urls, ["https://github.com"])
        self.assertEqual(self.runner.spawned, [["cmd", "/c", "start", "", "notepad"]])

    def test_an_unknown_name_opens_nothing_at_all(self):
        with self.assertRaises(AppError) as raised:
            self.service.open(["notepad", "youtube", "flappy penguin"])
        self.assertIn("flappy penguin", str(raised.exception))
        self.assertEqual(self.runner.started, 0)
        self.assertEqual(self.browser.urls, [])

    def test_whatsapp_opens_weronikas_own_window_and_reports_the_sign_in(self):
        shown = []

        def window(platform):
            shown.append(platform)
            return platform == "whatsapp"  # WhatsApp still waits for the QR code

        service = OpenService(SiteService(self.browser), self.apps, window)
        result = service.open(["whatsapp", "telegram web"])
        self.assertEqual(shown, ["whatsapp", "telegram"])
        self.assertEqual(self.runner.started, 0)  # not the Store app, although it is installed
        self.assertIn("WhatsApp in Weronika’s own browser window. It is not signed in yet: scan the QR code", result["message"])
        self.assertIn("Opened Telegram in Weronika’s own browser window. It is signed in", result["message"])
        self.assertEqual([entry["kind"] for entry in result["opened"]], ["chat", "chat"])

    def test_the_whatsapp_app_is_the_desktop_program(self):
        shown = []
        service = OpenService(SiteService(self.browser), self.apps, shown.append)
        service.open([{"name": "whatsapp", "kind": "app"}])
        self.assertEqual(shown, [])
        self.assertEqual(self.runner.spawned, [["explorer.exe", f"shell:AppsFolder\\{WHATSAPP_ID}"]])

    def test_a_chat_window_that_cannot_open_is_reported(self):
        def broken(platform):
            raise RuntimeError("Could not open the Whatsapp browser profile.")

        with self.assertRaises(AppError) as raised:
            OpenService(SiteService(self.browser), self.apps, broken).open("whatsapp")
        self.assertIn("browser profile", str(raised.exception))

    def test_refused_sites_stay_refused(self):
        with self.assertRaises(AppError) as raised:
            self.service.open(["notepad", "vegamovies"])
        self.assertIn("will not automate", str(raised.exception))
        self.assertEqual(self.runner.started, 0)

    def test_limits(self):
        with self.assertRaises(AppError):
            self.service.open([])
        with self.assertRaises(AppError):
            self.service.open(["youtube"] * 11)
        with self.assertRaises(AppError):
            self.service.open(["notepad", "calculator", "paint", "cmd", "settings", "camera"])
        self.assertEqual(self.runner.started, 0)


class OpenRouteTests(WindowsCase):
    """The routes on a real loopback server; the launcher records instead of starting."""

    def setUp(self):
        super().setUp()
        self.browser = FakeBrowser()
        self.workspace_dir = tempfile.TemporaryDirectory()
        self.own_browser = []
        tasks = SimpleNamespace(open_in_own_browser=lambda url, preferred: self.own_browser.append(url) or "ok")
        self.server = LocalServer(
            ("127.0.0.1", 0),
            make_handler(
                MessagingService(lambda _: None),
                SimpleNamespace(browser=self.browser),
                LocalWorkspace(self.workspace_dir.name),
                tasks=tasks,
                apps=self.apps,
            ),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.workspace_dir.cleanup()
        super().tearDown()

    def post(self, path, payload, headers=None):
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **(headers or {})},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
        return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]

    def test_open_starts_apps_and_sites(self):
        events = self.post("/api/open", {"targets": ["notepad", {"name": "youtube", "kind": "auto"}]})
        result = next(event for event in events if event["type"] == "result")["workflow"]
        self.assertEqual(result["count"], 2)
        self.assertEqual(self.runner.spawned, [["cmd", "/c", "start", "", "notepad"]])
        self.assertEqual(self.browser.urls, ["https://www.youtube.com/"])

    def test_open_accepts_plain_names(self):
        self.post("/api/open", {"names": ["calculator"]})
        self.post("/api/open", {"name": "paint"})
        self.assertEqual(
            self.runner.spawned,
            [["cmd", "/c", "start", "", "calc"], ["cmd", "/c", "start", "", "mspaint"]],
        )

    def test_an_unknown_name_is_reported_as_an_error_event(self):
        events = self.post("/api/open", {"names": ["flappy penguin"]})
        self.assertEqual(events[-1]["type"], "error")
        self.assertIn("flappy penguin", events[-1]["message"])
        self.assertEqual(self.runner.started, 0)

    def test_music_route(self):
        events = self.post("/api/apps/music", {"service": "spotify", "query": "tum hi ho"})
        result = next(event for event in events if event["type"] == "result")["workflow"]
        self.assertEqual(result["where"], "app")
        self.assertEqual(self.runner.files, ["spotify:search:tum%20hi%20ho"])

    def test_music_route_falls_back_to_the_own_browser(self):
        (self.menu / "Spotify.lnk").unlink()
        self.post("/api/apps/music", {"service": "spotify", "query": "tum hi ho"})
        self.assertEqual(self.own_browser, ["https://open.spotify.com/search/tum%20hi%20ho"])

    def test_a_page_from_another_site_cannot_start_apps(self):
        for headers in ({"Origin": "https://evil.example"}, {"Host": "evil.example"}):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.post("/api/open", {"names": ["notepad"]}, headers)
            self.assertEqual(raised.exception.code, 403)
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.post("/api/apps/music", {"service": "spotify", "query": "x"}, headers)
            self.assertEqual(raised.exception.code, 403)
        self.assertEqual(self.runner.started, 0)

    def test_status_reports_the_new_abilities(self):
        with urllib.request.urlopen(f"{self.base}/api/automation/status", timeout=5) as response:
            status = json.loads(response.read().decode("utf-8"))
        self.assertTrue(status["apps"])
        self.assertTrue(status["news"])


if __name__ == "__main__":
    unittest.main()
