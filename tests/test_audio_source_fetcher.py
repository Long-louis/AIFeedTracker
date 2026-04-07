import tempfile
import unittest
from pathlib import Path
from unittest import mock

from services.ai_summary.audio_source_fetcher import (
    AudioFetchErrorType,
    AudioSourceFetcher,
)


class TestAudioSourceFetcher(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    async def test_fetch_audio_returns_result_when_download_and_conversion_succeed(
        self,
    ):
        fetcher = AudioSourceFetcher(
            temp_dir=self.temp_dir.name,
            max_audio_minutes=30,
            cleanup_temp_files=True,
        )
        video_info = {
            "duration": 120,
            "cid": 123,
            "pages": [{"cid": 123, "page": 1}],
        }
        download_payload = {
            "dash": {
                "audio": [
                    {"id": 30216, "baseUrl": "https://cdn.example/audio-low.m4s"},
                    {"id": 30280, "baseUrl": "https://cdn.example/audio-high.m4s"},
                ]
            }
        }

        video_instance = mock.Mock()
        video_instance.get_info = mock.AsyncMock(return_value=video_info)
        video_instance.get_download_url = mock.AsyncMock(return_value=download_payload)

        async def fake_download(source_url, destination, referer):
            self.assertEqual(source_url, "https://cdn.example/audio-high.m4s")
            destination.write_bytes(b"source-bytes")
            return destination

        async def fake_normalize(source_path, output_path):
            self.assertTrue(source_path.exists())
            output_path.write_bytes(b"normalized-bytes")
            return output_path

        with mock.patch(
            "services.ai_summary.audio_source_fetcher.video.Video",
            return_value=video_instance,
        ):
            with mock.patch.object(
                fetcher, "_download_media", side_effect=fake_download
            ):
                with mock.patch.object(
                    fetcher, "_normalize_audio", side_effect=fake_normalize
                ):
                    result = await fetcher.fetch_audio(
                        "https://www.bilibili.com/video/BV1xx411c7mD"
                    )

        self.assertIsNotNone(result)
        self.assertEqual(result.video_id, "BV1xx411c7mD")
        self.assertEqual(result.duration_seconds, 120)
        self.assertTrue(Path(result.audio_path).is_file())
        self.assertTrue(Path(result.workspace).is_dir())
        self.assertEqual(fetcher.last_error_type, AudioFetchErrorType.NONE)
        self.assertIsNone(fetcher.last_error)

    async def test_fetch_audio_rejects_overlong_video_before_download(self):
        fetcher = AudioSourceFetcher(
            temp_dir=self.temp_dir.name,
            max_audio_minutes=1,
            cleanup_temp_files=True,
        )
        video_instance = mock.Mock()
        video_instance.get_info = mock.AsyncMock(
            return_value={"duration": 61, "cid": 123}
        )
        video_instance.get_download_url = mock.AsyncMock()

        with mock.patch(
            "services.ai_summary.audio_source_fetcher.video.Video",
            return_value=video_instance,
        ):
            result = await fetcher.fetch_audio(
                "https://www.bilibili.com/video/BV1xx411c7mD"
            )

        self.assertIsNone(result)
        self.assertEqual(
            fetcher.last_error_type, AudioFetchErrorType.AUDIO_DURATION_EXCEEDED
        )
        video_instance.get_download_url.assert_not_awaited()

    async def test_fetch_audio_allows_short_selected_page_when_archive_duration_is_long(
        self,
    ):
        fetcher = AudioSourceFetcher(
            temp_dir=self.temp_dir.name,
            max_audio_minutes=1,
            cleanup_temp_files=True,
        )
        video_info = {
            "duration": 600,
            "cid": 111,
            "pages": [
                {"cid": 111, "page": 1, "duration": 600},
                {"cid": 222, "page": 2, "duration": 45},
            ],
        }
        video_instance = mock.Mock()
        video_instance.get_info = mock.AsyncMock(return_value=video_info)
        video_instance.get_download_url = mock.AsyncMock(
            return_value={
                "dash": {
                    "audio": [
                        {"id": 30280, "baseUrl": "https://cdn.example/audio-high.m4s"}
                    ]
                }
            }
        )

        async def fake_download(source_url, destination, referer):
            destination.write_bytes(b"source-bytes")
            return destination

        async def fake_normalize(source_path, output_path):
            output_path.write_bytes(b"normalized-bytes")
            return output_path

        with mock.patch(
            "services.ai_summary.audio_source_fetcher.video.Video",
            return_value=video_instance,
        ):
            with mock.patch.object(
                fetcher, "_download_media", side_effect=fake_download
            ):
                with mock.patch.object(
                    fetcher, "_normalize_audio", side_effect=fake_normalize
                ):
                    result = await fetcher.fetch_audio(
                        "https://www.bilibili.com/video/BV1xx411c7mD?p=2"
                    )

        self.assertIsNotNone(result)
        self.assertEqual(result.duration_seconds, 45)
        self.assertEqual(fetcher.last_error_type, AudioFetchErrorType.NONE)
        video_instance.get_download_url.assert_awaited_once_with(page_index=1, cid=222)

    async def test_fetch_audio_returns_selected_page_duration_when_available(self):
        fetcher = AudioSourceFetcher(
            temp_dir=self.temp_dir.name,
            max_audio_minutes=30,
            cleanup_temp_files=True,
        )
        video_info = {
            "duration": 600,
            "cid": 111,
            "pages": [
                {"cid": 111, "page": 1, "duration": 600},
                {"cid": 222, "page": 2, "duration": 45},
            ],
        }
        video_instance = mock.Mock()
        video_instance.get_info = mock.AsyncMock(return_value=video_info)
        video_instance.get_download_url = mock.AsyncMock(
            return_value={
                "dash": {
                    "audio": [
                        {"id": 30280, "baseUrl": "https://cdn.example/audio-high.m4s"}
                    ]
                }
            }
        )

        async def fake_download(source_url, destination, referer):
            destination.write_bytes(b"source-bytes")
            return destination

        async def fake_normalize(source_path, output_path):
            output_path.write_bytes(b"normalized-bytes")
            return output_path

        with mock.patch(
            "services.ai_summary.audio_source_fetcher.video.Video",
            return_value=video_instance,
        ):
            with mock.patch.object(
                fetcher, "_download_media", side_effect=fake_download
            ):
                with mock.patch.object(
                    fetcher, "_normalize_audio", side_effect=fake_normalize
                ):
                    result = await fetcher.fetch_audio(
                        "https://www.bilibili.com/video/BV1xx411c7mD?p=2"
                    )

        self.assertIsNotNone(result)
        self.assertEqual(result.duration_seconds, 45)

    async def test_fetch_audio_sets_missing_source_error_when_no_stream_url_exists(
        self,
    ):
        fetcher = AudioSourceFetcher(
            temp_dir=self.temp_dir.name,
            max_audio_minutes=30,
            cleanup_temp_files=True,
        )
        video_instance = mock.Mock()
        video_instance.get_info = mock.AsyncMock(
            return_value={"duration": 120, "cid": 123}
        )
        video_instance.get_download_url = mock.AsyncMock(
            return_value={"dash": {}, "durl": []}
        )

        with mock.patch(
            "services.ai_summary.audio_source_fetcher.video.Video",
            return_value=video_instance,
        ):
            result = await fetcher.fetch_audio(
                "https://www.bilibili.com/video/BV1xx411c7mD"
            )

        self.assertIsNone(result)
        self.assertEqual(
            fetcher.last_error_type, AudioFetchErrorType.AUDIO_SOURCE_UNAVAILABLE
        )

    async def test_fetch_audio_returns_none_when_metadata_lookup_raises(self):
        fetcher = AudioSourceFetcher(
            temp_dir=self.temp_dir.name,
            max_audio_minutes=30,
            cleanup_temp_files=True,
        )
        video_instance = mock.Mock()
        video_instance.get_info = mock.AsyncMock(
            side_effect=RuntimeError("metadata failed")
        )
        video_instance.get_download_url = mock.AsyncMock()

        with mock.patch(
            "services.ai_summary.audio_source_fetcher.video.Video",
            return_value=video_instance,
        ):
            result = await fetcher.fetch_audio(
                "https://www.bilibili.com/video/BV1xx411c7mD"
            )

        self.assertIsNone(result)
        self.assertEqual(
            fetcher.last_error_type, AudioFetchErrorType.AUDIO_SOURCE_UNAVAILABLE
        )
        self.assertEqual(fetcher.last_error, "metadata failed")
        video_instance.get_download_url.assert_not_awaited()

    def test_cleanup_workspace_removes_directory(self):
        fetcher = AudioSourceFetcher(
            temp_dir=self.temp_dir.name,
            max_audio_minutes=30,
            cleanup_temp_files=True,
        )
        workspace = Path(self.temp_dir.name) / "BV1xx411c7mD-workspace"
        workspace.mkdir()
        (workspace / "audio.wav").write_bytes(b"audio")

        fetcher.cleanup_workspace(workspace)

        self.assertFalse(workspace.exists())

    def test_select_audio_source_prefers_dash_audio_then_falls_back_to_durl(self):
        fetcher = AudioSourceFetcher(
            temp_dir=self.temp_dir.name,
            max_audio_minutes=30,
            cleanup_temp_files=True,
        )

        dash_payload = {
            "dash": {
                "audio": [
                    {"id": 30216, "baseUrl": "https://cdn.example/audio-low.m4s"},
                    {"id": 30280, "baseUrl": "https://cdn.example/audio-high.m4s"},
                ]
            },
            "durl": [{"url": "https://cdn.example/fallback.mp4"}],
        }
        durl_payload = {"durl": [{"url": "https://cdn.example/fallback.mp4"}]}

        self.assertEqual(
            fetcher._select_audio_source(dash_payload),
            "https://cdn.example/audio-high.m4s",
        )
        self.assertEqual(
            fetcher._select_audio_source(durl_payload),
            "https://cdn.example/fallback.mp4",
        )


if __name__ == "__main__":
    unittest.main()
