from tools.lerobot_policy_leakage_gate import compact_info_payload, train_command


def test_compact_info_preserves_lerobot_storage_limits() -> None:
    source = {
        "codebase_version": "v3.0",
        "fps": 20,
        "features": {
            "observation.state": {"dtype": "float32", "shape": [6]},
            "observation.images.front": {"dtype": "video", "shape": [3, 480, 640]},
        },
        "total_episodes": 400,
        "total_frames": 120_735,
        "splits": {"train": "0:400"},
        "data_files_size_in_mb": 100,
        "video_files_size_in_mb": 200,
        "video_path": "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4",
    }

    compact = compact_info_payload(
        source_info=source,
        split_name="random_episode",
        partition="train",
        episode_count=320,
        frame_count=98_990,
    )

    assert compact["data_files_size_in_mb"] == 100
    assert compact["video_files_size_in_mb"] == 200
    assert compact["video_path"] is None
    assert compact["total_episodes"] == 320
    assert compact["total_frames"] == 98_990
    assert "observation.images.front" not in compact["features"]
    assert "worldepisode_split_package" not in compact


def test_train_command_uses_committed_local_dataset_root() -> None:
    command = train_command(
        policy="act",
        dataset_repo_id="worldepisode/example",
        dataset_root="docs/experiments/example",
        output_dir="outputs/example",
        job_name="example",
        device="cuda",
        steps=10,
        seed=17,
        wandb=False,
    )

    assert "--dataset.repo_id=worldepisode/example" in command
    assert "--dataset.root=docs/experiments/example" in command
    assert "--policy.push_to_hub=false" in command
