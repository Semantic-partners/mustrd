from mustrdTestPlugin import MustrdTestPlugin


def pytest_addoption(parser):
    #group = parser.getgroup("md summary")
    #group.addoption(
    #    "--md",
    #    action="store",
    #    dest="mdpath",
    #    metavar="path",
    #    default="junit/github_job_summary.md",
    #    help="create md summary file at that path.",
    #)
    return


def pytest_configure(config) -> None:

    #mdpath = config.getoption("mdpath")
#
    #if mdpath:
    #    config.pluginmanager.register(MustrdTestPlugin(mdpath))
    config.pluginmanager.register(MustrdTestPlugin())