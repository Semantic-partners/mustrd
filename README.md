# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Semantic-partners/mustrd/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                                |    Stmts |     Miss |   Cover |   Missing |
|-------------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| mustrd/TestResult.py                                                |       97 |        0 |    100% |           |
| mustrd/\_\_init\_\_.py                                              |        2 |        0 |    100% |           |
| mustrd/anzo\_utils.py                                               |       68 |       25 |     63% |77-85, 93-101, 105-110, 116, 120, 126-128, 134, 138, 143-159 |
| mustrd/cli.py                                                       |       90 |        5 |     94% |79, 163, 208-209, 242 |
| mustrd/config.py                                                    |       36 |        0 |    100% |           |
| mustrd/coverage.py                                                  |      229 |       12 |     95% |241, 312, 319, 331-333, 336, 339-340, 365, 373-374 |
| mustrd/coverage\_rdf.py                                             |      208 |       11 |     95% |30-31, 70, 120, 132, 140, 185-186, 192, 219, 229 |
| mustrd/coverage\_render.py                                          |      128 |        0 |    100% |           |
| mustrd/cq.py                                                        |       81 |        1 |     99% |        96 |
| mustrd/cq\_render.py                                                |       95 |        3 |     97% | 48, 66-67 |
| mustrd/logger\_setup.py                                             |       45 |       10 |     78% |     81-93 |
| mustrd/mustrd.py                                                    |      765 |      109 |     86% |55, 65-71, 218-232, 249-250, 264-266, 281-282, 289-295, 364-367, 382-413, 423, 432-435, 446, 477-487, 580, 623-624, 652-653, 660-663, 665-666, 696, 724, 865-866, 909-910, 1000, 1079, 1243-1244, 1282-1283, 1303-1304, 1368, 1380-1381, 1484-1501, 1505, 1519-1525, 1530-1532, 1537-1538, 1545-1546, 1551-1552, 1558, 1562, 1732, 1734, 1745, 1749-1750 |
| mustrd/mustrdAnzo.py                                                |       87 |       63 |     28% |10-21, 25-44, 48-55, 71-76, 80-94, 99-108, 111-122, 125-145, 148-158, 162-167 |
| mustrd/mustrdGraphDb.py                                             |       48 |       34 |     29% |12, 18-32, 36, 40, 44, 48-49, 53-62, 66-79, 83-96 |
| mustrd/mustrdRdfLib.py                                              |       35 |        6 |     83% |23-24, 37-38, 49-50 |
| mustrd/mustrdStardog.py                                             |       99 |       20 |     80% |93, 105, 117-118, 153-156, 161, 184-200 |
| mustrd/mustrdTestPlugin.py                                          |      341 |       52 |     85% |308, 337-339, 381, 383-385, 473-480, 524-526, 594-596, 613, 628-630, 643, 647, 649-650, 684, 689-691, 750, 758-759, 774, 777-778, 790-793, 796-797, 799-810 |
| mustrd/namespace.py                                                 |       18 |        1 |     94% |        79 |
| mustrd/ontology.py                                                  |      193 |       22 |     89% |74, 87, 148-151, 168, 180-181, 196-198, 201, 282-286, 329, 347-348, 350, 355-356 |
| mustrd/reporting.py                                                 |      232 |       23 |     90% |93, 110, 115-116, 120-121, 130, 173, 191-192, 221-222, 248, 269-270, 301, 303-305, 441-442, 444-445 |
| mustrd/results\_rdf.py                                              |       49 |        4 |     92% |64, 92-93, 99 |
| mustrd/runner.py                                                    |       76 |        5 |     93% |   151-155 |
| mustrd/sources\_rdf.py                                              |       73 |        4 |     95% |36-37, 39-40 |
| mustrd/spec\_component.py                                           |      488 |       93 |     81% |173, 235, 261, 268, 299, 306, 413, 419, 449-450, 469-471, 550-563, 567, 571, 575, 639-640, 646-654, 659-673, 678-689, 694-708, 713-735, 748, 765, 771, 775-776, 941-944, 953, 960, 967, 989-999, 1015-1019 |
| mustrd/steprunner.py                                                |      132 |       46 |     65% |42, 84-93, 98, 103, 124-145, 150-172, 188, 198-200, 213-214 |
| mustrd/utils.py                                                     |       29 |        5 |     83% |40-42, 48-49 |
| mustrd/viewer.py                                                    |       50 |        2 |     96% |    81, 86 |
| test/\_\_init\_\_.py                                                |        0 |        0 |    100% |           |
| test/addspec\_source\_file\_to\_spec\_graph.py                      |        8 |        0 |    100% |           |
| test/graph\_util.py                                                 |       10 |        8 |     20% |      5-13 |
| test/test\_anzo\_tls.py                                             |       33 |        0 |    100% |           |
| test/test\_cli.py                                                   |       65 |        0 |    100% |           |
| test/test\_construct\_spec.py                                       |      275 |        6 |     98% |128, 254, 355, 421, 546, 598 |
| test/test\_coverage.py                                              |      253 |        0 |    100% |           |
| test/test\_coverage\_plugin.py                                      |      157 |        0 |    100% |           |
| test/test\_coverage\_rdf.py                                         |       98 |        0 |    100% |           |
| test/test\_coverage\_render.py                                      |       53 |        0 |    100% |           |
| test/test\_example\_report\_is\_current.py                          |       65 |       14 |     78% |71, 75, 87-99, 126, 131 |
| test/test\_failure\_summary\_message.py                             |      114 |        0 |    100% |           |
| test/test\_general.py                                               |       59 |        1 |     98% |       143 |
| test/test\_graph\_aware\_then.py                                    |       84 |        0 |    100% |           |
| test/test\_mustrd\_anzo.py                                          |       59 |       16 |     73% |27-29, 34-36, 41-43, 48-50, 55-56, 61-62, 67-68, 73-74 |
| test/test\_mustrd\_stardog.py                                       |       94 |        0 |    100% |           |
| test/test\_no\_deprecation\_warnings.py                             |       97 |        0 |    100% |           |
| test/test\_pytest\_mustrd.py                                        |      111 |       15 |     86% |308-316, 446-469, 495 |
| test/test\_select\_spec.py                                          |      669 |       20 |     97% |131, 196, 264, 322, 450, 540, 598, 713, 836, 895, 950, 1015, 1087, 1167, 1283, 1346, 1408, 1469, 1650, 1923 |
| test/test\_spade\_edn\_group\_source.py                             |       27 |        2 |     93% |    61, 68 |
| test/test\_spec.py                                                  |      138 |        0 |    100% |           |
| test/test\_spec\_graph\_and\_given\_loading.py                      |       92 |        0 |    100% |           |
| test/test\_spec\_parser.py                                          |       57 |        0 |    100% |           |
| test/test\_then\_table\_result\_gives\_correct\_expected\_result.py |       31 |        4 |     87% |     68-71 |
| test/test\_update\_spec.py                                          |      278 |        6 |     98% |333, 391, 454, 517, 580, 757 |
| test/test\_viewer.py                                                |      227 |        1 |     99% |        55 |
| test/test\_viewer\_browser.py                                       |      100 |       67 |     33% |42-47, 67-78, 82-88, 94-103, 115-122, 127-145, 149-155, 159-164, 170-175, 181 |
| test/unit\_test.py                                                  |      150 |        0 |    100% |           |
| **TOTAL**                                                           | **7198** |  **716** | **90%** |           |


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