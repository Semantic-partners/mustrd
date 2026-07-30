# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Semantic-partners/mustrd/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                                |    Stmts |     Miss |   Cover |   Missing |
|-------------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| mustrd/TestResult.py                                                |       97 |        0 |    100% |           |
| mustrd/\_\_init\_\_.py                                              |        2 |        0 |    100% |           |
| mustrd/anzo\_utils.py                                               |       49 |       32 |     35% |16-24, 32-40, 44-49, 54-63, 67-69, 75, 79, 84-100 |
| mustrd/cli.py                                                       |       90 |        5 |     94% |79, 163, 208-209, 242 |
| mustrd/config.py                                                    |       36 |        0 |    100% |           |
| mustrd/coverage.py                                                  |      229 |       12 |     95% |241, 312, 319, 331-333, 336, 339-340, 365, 373-374 |
| mustrd/coverage\_rdf.py                                             |      208 |       11 |     95% |30-31, 70, 120, 132, 140, 185-186, 192, 219, 229 |
| mustrd/coverage\_render.py                                          |      128 |        0 |    100% |           |
| mustrd/cq.py                                                        |       81 |        1 |     99% |        96 |
| mustrd/cq\_render.py                                                |       95 |        3 |     97% | 48, 66-67 |
| mustrd/logger\_setup.py                                             |       45 |       10 |     78% |     81-93 |
| mustrd/mustrd.py                                                    |      575 |      132 |     77% |50-56, 189, 203-217, 234-235, 249-251, 266-267, 274-280, 303-307, 342-345, 360-391, 401, 410-413, 424, 455-465, 504-505, 517-518, 534-535, 542-546, 548-549, 561, 587, 635-636, 674-676, 685-686, 784, 916-933, 937-962, 1127, 1129, 1140, 1144-1179 |
| mustrd/mustrdAnzo.py                                                |       87 |       63 |     28% |10-21, 25-44, 48-55, 71-76, 80-94, 99-108, 111-122, 125-145, 148-158, 162-167 |
| mustrd/mustrdGraphDb.py                                             |       56 |       43 |     23% |9-19, 23-37, 41, 45, 49, 53-54, 58-67, 71-84, 88-101 |
| mustrd/mustrdRdfLib.py                                              |       31 |        6 |     81% |12-13, 27-28, 38-39 |
| mustrd/mustrdTestPlugin.py                                          |      266 |       36 |     86% |286, 302, 331-333, 435-442, 486-488, 543-545, 604, 609-611, 631-634, 637-638, 640-651 |
| mustrd/namespace.py                                                 |       18 |        1 |     94% |        74 |
| mustrd/ontology.py                                                  |      193 |       22 |     89% |74, 87, 148-151, 168, 180-181, 196-198, 201, 282-286, 329, 347-348, 350, 355-356 |
| mustrd/reporting.py                                                 |      227 |       22 |     90% |91, 108, 113-114, 118-119, 128, 176-177, 206-207, 233, 254-255, 286, 288-290, 426-427, 429-430 |
| mustrd/results\_rdf.py                                              |       49 |        4 |     92% |64, 92-93, 99 |
| mustrd/runner.py                                                    |       76 |        6 |     92% |95, 150-154 |
| mustrd/sources\_rdf.py                                              |       73 |        4 |     95% |36-37, 39-40 |
| mustrd/spec\_component.py                                           |      472 |      121 |     74% |112, 174, 222, 265-267, 333, 339, 350-351, 357-359, 397-410, 414, 418, 422, 475-486, 491-509, 514-531, 536-555, 560-585, 598, 605-649, 658, 664, 668-669, 805-808, 817, 824, 831, 853-863, 879-883 |
| mustrd/steprunner.py                                                |      141 |       50 |     65% |41, 46, 61-70, 75, 80, 85, 90, 95, 116-137, 142-164, 180, 187-189, 202-203 |
| mustrd/utils.py                                                     |       10 |        2 |     80% |     13-14 |
| mustrd/viewer.py                                                    |       50 |        2 |     96% |    81, 86 |
| test/\_\_init\_\_.py                                                |        0 |        0 |    100% |           |
| test/addspec\_source\_file\_to\_spec\_graph.py                      |        8 |        0 |    100% |           |
| test/graph\_util.py                                                 |       10 |        8 |     20% |      5-13 |
| test/test\_cli.py                                                   |       65 |        0 |    100% |           |
| test/test\_construct\_spec.py                                       |      275 |        6 |     98% |128, 254, 355, 421, 546, 598 |
| test/test\_coverage.py                                              |      253 |        0 |    100% |           |
| test/test\_coverage\_plugin.py                                      |      157 |        0 |    100% |           |
| test/test\_coverage\_rdf.py                                         |       98 |        0 |    100% |           |
| test/test\_coverage\_render.py                                      |       53 |        0 |    100% |           |
| test/test\_example\_report\_is\_current.py                          |       65 |       14 |     78% |71, 75, 87-99, 126, 131 |
| test/test\_general.py                                               |       37 |        1 |     97% |        80 |
| test/test\_mustrd\_anzo.py                                          |       59 |       16 |     73% |27-29, 34-36, 41-43, 48-50, 55-56, 61-62, 67-68, 73-74 |
| test/test\_pytest\_mustrd.py                                        |       83 |       15 |     82% |263-271, 346-369, 395 |
| test/test\_select\_spec.py                                          |      584 |       20 |     97% |129, 194, 262, 320, 448, 538, 596, 711, 834, 893, 948, 1013, 1085, 1165, 1279, 1339, 1401, 1462, 1643, 1913 |
| test/test\_spade\_edn\_group\_source.py                             |       27 |        2 |     93% |    61, 68 |
| test/test\_spec.py                                                  |      117 |        0 |    100% |           |
| test/test\_spec\_parser.py                                          |       56 |        0 |    100% |           |
| test/test\_then\_table\_result\_gives\_correct\_expected\_result.py |       31 |        4 |     87% |     68-71 |
| test/test\_update\_spec.py                                          |      278 |        6 |     98% |333, 391, 454, 517, 580, 757 |
| test/test\_viewer.py                                                |      227 |        1 |     99% |        55 |
| test/test\_viewer\_browser.py                                       |      100 |       67 |     33% |42-47, 67-78, 82-88, 94-103, 115-122, 127-145, 149-155, 159-164, 170-175, 181 |
| test/unit\_test.py                                                  |      106 |        0 |    100% |           |
| **TOTAL**                                                           | **6073** |  **748** | **88%** |           |


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