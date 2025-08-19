# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Semantic-partners/mustrd/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                                |    Stmts |     Miss |   Cover |   Missing |
|-------------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| mustrd/TestResult.py                                                |       78 |       34 |     56% |63-68, 79-82, 86-94, 106-109, 112-131, 134-136 |
| mustrd/\_\_init\_\_.py                                              |        0 |        0 |    100% |           |
| mustrd/anzo\_utils.py                                               |       49 |       32 |     35% |40-48, 56-64, 68-73, 78-87, 91-93, 99, 103, 108-124 |
| mustrd/logger\_setup.py                                             |       20 |        2 |     90% |     52-53 |
| mustrd/mustrd.py                                                    |      598 |      160 |     73% |47-53, 186, 200-214, 231-232, 246-248, 263-264, 271-277, 300-304, 338-341, 356-387, 397, 406-409, 420, 452-462, 501-502, 514-515, 527, 531-532, 536, 539-543, 545-546, 557-563, 584, 632-633, 671-673, 682-683, 781, 913-930, 934-959, 1048-1137, 1141-1176 |
| mustrd/mustrdAnzo.py                                                |       84 |       68 |     19% |10-21, 25-44, 48-55, 59-63, 68-73, 77-91, 96-105, 108-119, 122-142, 145-155, 159-164 |
| mustrd/mustrdGraphDb.py                                             |       56 |       43 |     23% |33-43, 47-61, 65, 69, 73, 77-78, 82-91, 95-108, 112-125 |
| mustrd/mustrdRdfLib.py                                              |       31 |        6 |     81% |36-37, 51-52, 62-63 |
| mustrd/mustrdTestPlugin.py                                          |      245 |       62 |     75% |226, 234-236, 282-294, 334-371, 415-417, 474-476, 481-483, 492-493, 498-526 |
| mustrd/namespace.py                                                 |       83 |        1 |     99% |        98 |
| mustrd/spec\_component.py                                           |      479 |      121 |     75% |135, 188, 236, 279-281, 347, 353, 364-365, 371-373, 411-424, 428, 432, 436, 486-497, 502-520, 525-542, 547-566, 571-596, 609, 616-660, 669, 675, 679-680, 815-818, 827, 834, 841, 863-873, 889-893 |
| mustrd/steprunner.py                                                |      141 |       50 |     65% |65, 70, 85-94, 99, 104, 109, 114, 119, 140-161, 166-188, 204, 211-213, 226-227 |
| mustrd/utils.py                                                     |       10 |        2 |     80% |     37-38 |
| test/\_\_init\_\_.py                                                |        0 |        0 |    100% |           |
| test/addspec\_source\_file\_to\_spec\_graph.py                      |        8 |        0 |    100% |           |
| test/graph\_util.py                                                 |       10 |        8 |     20% |     29-37 |
| test/test\_construct\_spec.py                                       |      275 |        6 |     98% |152, 278, 379, 445, 570, 622 |
| test/test\_general.py                                               |       37 |        1 |     97% |        80 |
| test/test\_mustrd\_anzo.py                                          |       46 |       16 |     65% |27-29, 34-36, 41-43, 48-50, 55-56, 61-62, 67-68, 73-74 |
| test/test\_pytest\_mustrd.py                                        |       83 |       15 |     82% |255-263, 338-361, 387 |
| test/test\_select\_spec.py                                          |      584 |       20 |     97% |129, 194, 262, 320, 448, 538, 596, 711, 834, 893, 948, 1013, 1085, 1165, 1279, 1339, 1401, 1462, 1643, 1913 |
| test/test\_spade\_edn\_group\_source.py                             |       27 |        2 |     93% |    61, 68 |
| test/test\_spec.py                                                  |      117 |        0 |    100% |           |
| test/test\_spec\_parser.py                                          |       56 |        0 |    100% |           |
| test/test\_then\_table\_result\_gives\_correct\_expected\_result.py |       31 |        4 |     87% |     93-96 |
| test/test\_update\_spec.py                                          |      278 |        6 |     98% |333, 391, 454, 517, 580, 757 |
| test/unit\_test.py                                                  |      106 |        0 |    100% |           |
|                                                           **TOTAL** | **3532** |  **659** | **81%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/Semantic-partners/mustrd/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/Semantic-partners/mustrd/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Semantic-partners/mustrd/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/Semantic-partners/mustrd/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2FSemantic-partners%2Fmustrd%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/Semantic-partners/mustrd/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.