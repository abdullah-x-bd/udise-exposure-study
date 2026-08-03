from udise.comprehensive_a0_staged import BATCH_SIZE, MEMORY_LIMIT, batches


def test_staged_runner_uses_bounded_memory_and_batches() -> None:
    assert MEMORY_LIMIT == "4GB"
    assert BATCH_SIZE == 10
    assert list(batches(tuple(range(23)))) == [
        tuple(range(10)),
        tuple(range(10, 20)),
        tuple(range(20, 23)),
    ]
