from devlog import main


def test_devlog_command_runs(capsys):
    main()

    assert capsys.readouterr().out == "Hello from devlog!\n"
