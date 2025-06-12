# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Semantic-partners/mustrd/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                                |    Stmts |     Miss |   Cover |   Missing |
|-------------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| mustrd/TestResult.py                                                |       78 |       34 |     56% |63-68, 79-82, 86-94, 106-109, 112-131, 134-136 |
| mustrd/\_\_init\_\_.py                                              |        0 |        0 |    100% |           |
| mustrd/anzo\_utils.py                                               |       49 |       32 |     35% |40-48, 56-64, 68-73, 78-87, 91-93, 99, 103, 108-124 |
| mustrd/logger\_setup.py                                             |       20 |        2 |     90% |     52-53 |
| mustrd/mustrd.py                                                    |      597 |      159 |     73% |47-53, 185, 199-207, 224-225, 239-241, 256-257, 264-270, 293-297, 331-334, 349-380, 390, 399-402, 413, 445-455, 494-495, 507-508, 520, 524-525, 530, 533-537, 539-540, 551-557, 578, 626-627, 665-667, 676-677, 775, 907-924, 928-953, 1042-1131, 1135-1170 |
| mustrd/mustrdAnzo.py                                                |       82 |       66 |     20% |34-45, 49-68, 72-79, 83-87, 92-97, 101-115, 120-129, 132-143, 146-166, 169-178, 182-186 |
| mustrd/mustrdGraphDb.py                                             |       56 |       43 |     23% |33-43, 47-61, 65, 69, 73, 77-78, 82-91, 95-108, 112-125 |
| mustrd/mustrdRdfLib.py                                              |       31 |        6 |     81% |36-37, 51-52, 62-63 |
| mustrd/mustrdTestPlugin.py                                          |      257 |       58 |     77% |231, 239-241, 297-304, 309-321, 361-398, 449-451, 508-510, 515-517, 526-527, 532-549 |
| mustrd/namespace.py                                                 |       83 |        1 |     99% |        98 |
| mustrd/spec\_component.py                                           |      474 |      117 |     75% |135, 188, 236, 279-281, 347, 353, 364-365, 371-373, 411-424, 428, 432, 436, 486-497, 502-520, 525-542, 547-566, 571-596, 609, 616-660, 669, 675, 679-680, 815-818, 827, 834, 841, 862-863, 877-881 |
| mustrd/steprunner.py                                                |      133 |       44 |     67% |65, 70, 85-94, 99, 104, 109, 114, 119, 140-161, 166-181, 199-201, 214-215 |
| mustrd/utils.py                                                     |       10 |        2 |     80% |     37-38 |
| test/\_\_init\_\_.py                                                |        0 |        0 |    100% |           |
| test/addspec\_source\_file\_to\_spec\_graph.py                      |        8 |        0 |    100% |           |
| test/graph\_util.py                                                 |       10 |        8 |     20% |     29-37 |
| test/test\_construct\_spec.py                                       |      275 |        6 |     98% |152, 278, 379, 445, 570, 622 |
| test/test\_general.py                                               |       37 |        1 |     97% |        80 |
| test/test\_mustrd\_anzo.py                                          |       46 |       16 |     65% |27-29, 34-36, 41-43, 48-50, 55-56, 61-62, 67-68, 73-74 |
| test/test\_pytest\_mustrd.py                                        |       83 |       15 |     82% |246-254, 329-352, 378 |
| test/test\_select\_spec.py                                          |      584 |       20 |     97% |129, 194, 262, 320, 448, 538, 596, 711, 834, 893, 948, 1013, 1085, 1165, 1279, 1339, 1401, 1462, 1643, 1913 |
| test/test\_spade\_edn\_group\_source.py                             |       26 |        2 |     92% |    62, 70 |
| test/test\_spec.py                                                  |      117 |        0 |    100% |           |
| test/test\_spec\_parser.py                                          |       56 |        0 |    100% |           |
| test/test\_then\_table\_result\_gives\_correct\_expected\_result.py |       31 |        4 |     87% |     93-96 |
| test/test\_update\_spec.py                                          |      278 |        6 |     98% |333, 391, 454, 517, 580, 757 |
| test/unit\_test.py                                                  |      106 |        0 |    100% |           |
|                                                           **TOTAL** | **3527** |  **642** | **82%** |           |


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