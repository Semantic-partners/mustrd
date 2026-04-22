# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Semantic-partners/mustrd/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                                |    Stmts |     Miss |   Cover |   Missing |
|-------------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| mustrd/TestResult.py                                                |       64 |       34 |     47% |39-44, 55-58, 62-70, 82-85, 88-107, 110-112 |
| mustrd/\_\_init\_\_.py                                              |        0 |        0 |    100% |           |
| mustrd/anzo\_utils.py                                               |       49 |       32 |     35% |16-24, 32-40, 44-49, 54-63, 67-69, 75, 79, 84-100 |
| mustrd/logger\_setup.py                                             |       20 |       12 |     40% |11-24, 28-29 |
| mustrd/mustrd.py                                                    |      579 |      160 |     72% |47-53, 186, 200-214, 231-232, 246-248, 263-264, 271-277, 300-304, 339-342, 357-388, 398, 407-410, 421, 453-463, 502-503, 515-516, 528, 532-533, 537, 540-544, 546-547, 558-564, 585, 633-634, 672-674, 683-684, 782, 914-931, 935-960, 1049-1138, 1142-1177 |
| mustrd/mustrdAnzo.py                                                |       87 |       63 |     28% |10-21, 25-44, 48-55, 71-76, 80-94, 99-108, 111-122, 125-145, 148-158, 162-167 |
| mustrd/mustrdGraphDb.py                                             |       56 |       43 |     23% |9-19, 23-37, 41, 45, 49, 53-54, 58-67, 71-84, 88-101 |
| mustrd/mustrdRdfLib.py                                              |       31 |        6 |     81% |12-13, 27-28, 38-39 |
| mustrd/mustrdTestPlugin.py                                          |      234 |       62 |     74% |227, 235-237, 283-295, 335-372, 416-418, 475-477, 482-484, 493-494, 499-527 |
| mustrd/namespace.py                                                 |       14 |        1 |     93% |        74 |
| mustrd/spec\_component.py                                           |      473 |      121 |     74% |112, 165, 213, 256-258, 324, 330, 341-342, 348-350, 388-401, 405, 409, 413, 463-474, 479-497, 502-519, 524-543, 548-573, 586, 593-637, 646, 652, 656-657, 793-796, 805, 812, 819, 841-851, 867-871 |
| mustrd/steprunner.py                                                |      141 |       50 |     65% |41, 46, 61-70, 75, 80, 85, 90, 95, 116-137, 142-164, 180, 187-189, 202-203 |
| mustrd/utils.py                                                     |       10 |        2 |     80% |     13-14 |
| test/\_\_init\_\_.py                                                |        0 |        0 |    100% |           |
| test/addspec\_source\_file\_to\_spec\_graph.py                      |        8 |        0 |    100% |           |
| test/graph\_util.py                                                 |       10 |        8 |     20% |      5-13 |
| test/test\_construct\_spec.py                                       |      275 |        6 |     98% |128, 254, 355, 421, 546, 598 |
| test/test\_general.py                                               |       37 |        1 |     97% |        80 |
| test/test\_mustrd\_anzo.py                                          |       59 |       16 |     73% |27-29, 34-36, 41-43, 48-50, 55-56, 61-62, 67-68, 73-74 |
| test/test\_pytest\_mustrd.py                                        |       83 |       15 |     82% |263-271, 346-369, 395 |
| test/test\_select\_spec.py                                          |      584 |       20 |     97% |129, 194, 262, 320, 448, 538, 596, 711, 834, 893, 948, 1013, 1085, 1165, 1279, 1339, 1401, 1462, 1643, 1913 |
| test/test\_spade\_edn\_group\_source.py                             |       27 |        2 |     93% |    61, 68 |
| test/test\_spec.py                                                  |      117 |        0 |    100% |           |
| test/test\_spec\_parser.py                                          |       56 |        0 |    100% |           |
| test/test\_then\_table\_result\_gives\_correct\_expected\_result.py |       31 |        4 |     87% |     68-71 |
| test/test\_update\_spec.py                                          |      278 |        6 |     98% |333, 391, 454, 517, 580, 757 |
| test/unit\_test.py                                                  |      106 |        0 |    100% |           |
| **TOTAL**                                                           | **3429** |  **664** | **81%** |           |


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