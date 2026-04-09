<details>
<summary>
Pytest: <br/> total: 2, success: 2, fail: 0, skipped: 0
</summary>
<div>
<details>
<summary>
False: <br/> total: 2, success: 2, fail: 0, skipped: 0
</summary>
<div>
<style>
table.mustrd-main { border-collapse: collapse; width: 100%; font-size: 0.9em; }
table.mustrd-main th, table.mustrd-main td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; vertical-align: top; }
table.mustrd-main th { background: #f0f0f0; font-weight: bold; }
table.detail-table { border-collapse: collapse; font-size: 0.85em; width: 100%; margin-top: 4px; }
table.detail-table th, table.detail-table td { border: 1px solid #ddd; padding: 4px 10px; text-align: left; vertical-align: top; }
table.detail-table th { background: #eef; width: 160px; }
table.diff-table { border-collapse: collapse; font-size: 0.85em; margin-top: 4px; }
table.diff-table th, table.diff-table td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; white-space: nowrap; }
table.diff-table th { background: #f0f0f0; font-weight: bold; }
.status-passed { color: green; font-weight: bold; }
.status-failed { color: red; font-weight: bold; }
.status-skipped { color: grey; }
</style>
<table class="mustrd-main">
<thead><tr><th>module</th><th>class</th><th>test</th><th>status</th><th>details</th></tr></thead>
<tbody>
<tr>
<td>mustrd_config.ttl</td>
<td>hub_stations_ontology</td>
<td>hub_stations.mustrd.ttl</td>
<td><span class="status-passed">passed</span></td>
<td><details><summary>show</summary>
<table class="detail-table">
<tr><th>input file(s)</th><td><details><summary>/Users/pelolson-sp/mustrd/new_feature_ontology/minimal_train_triples.ttl</summary><pre>@prefix owl:  &lt;http://www.w3.org/2002/07/owl#&gt; .
@prefix rdfs: &lt;http://www.w3.org/2000/01/rdf-schema#&gt; .
@prefix xsd:  &lt;http://www.w3.org/2001/XMLSchema#&gt; .
@prefix skos: &lt;https://www.w3.org/2009/08/skos-reference/skos.html#&gt; .
@prefix :  &lt;https://example.org/trains-Triples#&gt; .
@prefix trains:     &lt;https://example.org/trains-Ontology#&gt; .
# Transport Modes
:Underground   a trains:TransportMode ; skos:prefLabel &quot;London Underground&quot; .
:Overground    a trains:TransportMode ; skos:prefLabel &quot;London Overground&quot; .
:ElizabethLine a trains:TransportMode ; skos:prefLabel &quot;Elizabeth line&quot; .
:DLR           a trains:TransportMode ; skos:prefLabel &quot;Docklands Light Railway&quot; .
:NationalRail  a trains:TransportMode ; skos:prefLabel &quot;National Rail&quot; .
# Zones
:Zone1 a trains:Zone ; skos:prefLabel &quot;Zone 1&quot; .
:Zone2 a trains:Zone ; skos:prefLabel &quot;Zone 2&quot; .
:Zone3 a trains:Zone ; skos:prefLabel &quot;Zone 3&quot; .
:Zone4 a trains:Zone ; skos:prefLabel &quot;Zone 4&quot; .
# Lines
:CentralLine
    a trains:Line ;
    skos:prefLabel &quot;Central&quot; ;
    trains:operatedBy :Underground .
:JubileeLine
    a trains:Line ;
    skos:prefLabel &quot;Jubilee&quot; ;
    trains:operatedBy :Underground .
:NorthernLine
    a trains:Line ;
    skos:prefLabel &quot;Northern&quot; ;
    trains:operatedBy :Underground .
:VictoriaLine
    a trains:Line ;
    skos:prefLabel &quot;Victoria&quot; ;
    trains:operatedBy :Underground .
:ElizabethLineSvc
    a trains:Line ;
    skos:prefLabel &quot;Elizabeth&quot; ;
    trains:operatedBy :ElizabethLine .
:DLRLine
    a trains:Line ;
    skos:prefLabel &quot;Docklands Light Railway&quot; ;
    trains:operatedBy :DLR .
:GWR
    a trains:Line ;
    skos:prefLabel &quot;Great Western Railway&quot; ;
    trains:operatedBy :NationalRail .
:LNER
    a trains:Line ;
    skos:prefLabel &quot;London North Eastern Railway&quot; ;
    trains:operatedBy :NationalRail .
:Southern
    a trains:Line ;
    skos:prefLabel &quot;Southern&quot; ;
    trains:operatedBy :NationalRail .
# Stations
:OxfordCircus
    a trains:Station ;
    skos:prefLabel &quot;Oxford Circus&quot; ;
    trains:inZone :Zone1 .
:BondStreet
    a trains:Station ;
    skos:prefLabel &quot;Bond Street&quot; ;
    trains:inZone :Zone1 .
:LiverpoolStreet
    a trains:Station ;
    skos:prefLabel &quot;Liverpool Street&quot; ;
    trains:inZone :Zone1 .
:StratfordStation
    a trains:Station ;
    skos:prefLabel &quot;Stratford&quot; ;
    trains:inZone :Zone3 .
:CanaryWharf
    a trains:Station ;
    skos:prefLabel &quot;Canary Wharf&quot; ;
    trains:inZone :Zone2 .
:KingsCross
    a trains:Station ;
    skos:prefLabel &quot;King&#x27;s Cross St. Pancras&quot; ;
    trains:inZone :Zone1 .
:BankStation
    a trains:Station ;
    skos:prefLabel &quot;Bank&quot; ;
    trains:inZone :Zone1 .
# trains:contradiction a trains:Station .
:WaterlooStation
    a trains:Station ;
    skos:prefLabel &quot;Waterloo&quot; ;
    trains:inZone :Zone1 .
:BrixtonStation
    a trains:Station ;
    skos:prefLabel &quot;Brixton&quot; ;
    trains:inZone :Zone2 .
:EalingBroadway
    a trains:Station ;
    skos:prefLabel &quot;Ealing Broadway&quot; ;
    trains:inZone :Zone3 .
:Paddington
    a trains:Station ;
    skos:prefLabel &quot;Paddington&quot; ;
    trains:inZone :Zone1 .
:TowerGateway
    a trains:Station ;
    skos:prefLabel &quot;Tower Gateway&quot; ;
    trains:inZone :Zone1 .
:Shadwell
    a trains:Station ;
    skos:prefLabel &quot;Shadwell&quot; ;
    trains:inZone :Zone2 .
:Limehouse
    a trains:Station ;
    skos:prefLabel &quot;Limehouse&quot; ;
    trains:inZone :Zone2 .
:Poplar
    a trains:Station ;
    skos:prefLabel &quot;Poplar&quot; ;
    trains:inZone :Zone2 .
:Westferry
    a trains:Station ;
    skos:prefLabel &quot;Westferry&quot; ;
    trains:inZone :Zone2 .
:HeronQuays
    a trains:Station ;
    skos:prefLabel &quot;Heron Quays&quot; ;
    trains:inZone :Zone2 .
# Line-station relationships
:CentralLine
    trains:hasStation :OxfordCircus ;
    trains:hasStation :BondStreet ;
    trains:hasStation :BankStation ;
    trains:hasStation :LiverpoolStreet ;
    trains:hasStation :EalingBroadway .
:JubileeLine
    trains:hasStation :BondStreet ;
    trains:hasStation :WaterlooStation ;
    trains:hasStation :CanaryWharf ;
    trains:hasStation :StratfordStation .
:NorthernLine
    trains:hasStation :KingsCross ;
    trains:hasStation :BankStation ;
    trains:hasStation :WaterlooStation ;
    trains:hasStation :BrixtonStation .
:VictoriaLine
    trains:hasStation :OxfordCircus ;
    trains:hasStation :KingsCross ;
    trains:hasStation :WaterlooStation ;
    trains:hasStation :BrixtonStation .
:ElizabethLineSvc
    trains:hasStation :BondStreet ;
    trains:hasStation :LiverpoolStreet ;
    trains:hasStation :CanaryWharf ;
    trains:hasStation :StratfordStation .
:GWR
    trains:hasStation :Paddington ;
    trains:hasStation :Reading ;
    trains:hasStation :BristolTempleMeads .
:LNER
    trains:hasStation :KingsCross ;
    trains:hasStation :York ;
    trains:hasStation :EdinburghWaverley .
:Southern
    trains:hasStation :LondonBridge ;
    trains:hasStation :GatwickAirport ;
    trains:hasStation :Brighton .
:DLRLine
    trains:hasStation :BankStation ;
    trains:hasStation :TowerGateway ;
    trains:hasStation :Shadwell ;
    trains:hasStation :Limehouse ;
    trains:hasStation :Westferry ;
    trains:hasStation :Poplar ;
    trains:hasStation :HeronQuays ;
    trains:hasStation :CanaryWharf ;
    trains:hasStation :StratfordStation .
</pre></details></td></tr>
<tr><th>ontology file(s)</th><td><details><summary>/Users/pelolson-sp/mustrd/new_feature_ontology/train_ontology.ttl</summary><pre>@prefix owl:  &lt;http://www.w3.org/2002/07/owl#&gt; .
@prefix rdfs: &lt;http://www.w3.org/2000/01/rdf-schema#&gt; .
@prefix xsd:  &lt;http://www.w3.org/2001/XMLSchema#&gt; .
@prefix skos: &lt;https://www.w3.org/2009/08/skos-reference/skos.html#&gt; .
@prefix :  &lt;https://example.org/trains-Ontology#&gt; .
&lt;https://example.org/trains-Ontology&gt;
    a owl:Ontology ;
    skos:prefLabel &quot;London Trains Ontology&quot; ;
    rdfs:comment &quot;A simple ontology describing rail concepts within London.&quot; .
# Classes
:TransportMode
    a owl:Class ;
    skos:prefLabel &quot;Transport Mode&quot; ;
    rdfs:comment &quot;A mode of transport available in London.&quot; .
:Line
    a owl:Class ;
    skos:prefLabel &quot;Line&quot; ;
    rdfs:comment &quot;A named service line (e.g. Central line, Elizabeth line).&quot; .
:TflLine a owl:Class ; skos:prefLabel &quot;TfL Line&quot; ; rdfs:comment &quot;Lines ran by Transport for London&quot; ; rdfs:subClassOf :Line .
:Station
    a owl:Class ;
    skos:prefLabel &quot;Station&quot; ;
    rdfs:comment &quot;A station or stop on the trains network.&quot; ;
    owl:disjointWith :Zone .
:Zone
    a owl:Class ;
    skos:prefLabel &quot;Zone&quot; ;
    rdfs:comment &quot;A fare zone in the trains network.&quot; ;
    owl:disjointWith :Station .
# :contradiction a owl:Class  ;
#         rdfs:subClassOf :Zone , :Station .
# :contradiction a :Zone .
# Properties
:operatedBy
    a owl:ObjectProperty ;
    skos:prefLabel &quot;operated by&quot; ;
    rdfs:domain :Line ;
    rdfs:comment &quot;connects a Line to the mode of transport it is part of&quot;;
    rdfs:range :TransportMode .
:hasStation
    a owl:ObjectProperty ;
    skos:prefLabel &quot;has station&quot; ;
    rdfs:comment &quot;connects a Station to a Line which stops there&quot;;
    rdfs:domain :Line ;
    rdfs:range :Station .
:inZone
    a owl:ObjectProperty ;
    skos:prefLabel &quot;in zone&quot; ;
    rdfs:comment &quot;connects a Station to the London fare zone it is part of&quot;;
    rdfs:domain :Station ;
    rdfs:range :Zone .
</pre></details></td></tr>
<tr><th>ontology conforms</th><td>✓</td></tr>
<tr><th>SHACL file(s)</th><td>—</td></tr>
<tr><th>SHACL conforms</th><td>—</td></tr>
</table>
</details></td>
</tr>
<tr>
<td>mustrd_config.ttl</td>
<td>hub_stations_shacl</td>
<td>hub_stations.mustrd.ttl</td>
<td><span class="status-passed">passed</span></td>
<td><details><summary>show</summary>
<table class="detail-table">
<tr><th>input file(s)</th><td><details><summary>/Users/pelolson-sp/mustrd/new_feature_shacl/minimal_train_triples.ttl</summary><pre>@prefix owl:  &lt;http://www.w3.org/2002/07/owl#&gt; .
@prefix rdfs: &lt;http://www.w3.org/2000/01/rdf-schema#&gt; .
@prefix xsd:  &lt;http://www.w3.org/2001/XMLSchema#&gt; .
@prefix skos: &lt;https://www.w3.org/2009/08/skos-reference/skos.html#&gt; .
@prefix :  &lt;https://example.org/trains-Triples#&gt; .
@prefix trains:     &lt;https://example.org/trains-Ontology#&gt; .
# Transport Modes
:Underground   a trains:TransportMode ; skos:prefLabel &quot;London Underground&quot; .
:Overground    a trains:TransportMode ; skos:prefLabel &quot;London Overground&quot; .
:ElizabethLine a trains:TransportMode ; skos:prefLabel &quot;Elizabeth line&quot; .
:DLR           a trains:TransportMode ; skos:prefLabel &quot;Docklands Light Railway&quot; .
:NationalRail  a trains:TransportMode ; skos:prefLabel &quot;National Rail&quot; .
# Zones
:Zone1 a trains:Zone ; skos:prefLabel &quot;Zone 1&quot; .
:Zone2 a trains:Zone ; skos:prefLabel &quot;Zone 2&quot; .
:Zone3 a trains:Zone ; skos:prefLabel &quot;Zone 3&quot; .
:Zone4 a trains:Zone ; skos:prefLabel &quot;Zone 4&quot; .
# Lines
:CentralLine
    a trains:Line ;
    skos:prefLabel &quot;Central&quot; ;
    trains:operatedBy :Underground .
:JubileeLine
    a trains:Line ;
    skos:prefLabel &quot;Jubilee&quot; ;
    trains:operatedBy :Underground .
:NorthernLine
    a trains:Line ;
    skos:prefLabel &quot;Northern&quot; ;
    trains:operatedBy :Underground .
:VictoriaLine
    a trains:Line ;
    skos:prefLabel &quot;Victoria&quot; ;
    trains:operatedBy :Underground .
:ElizabethLineSvc
    a trains:Line ;
    skos:prefLabel &quot;Elizabeth&quot; ;
    trains:operatedBy :ElizabethLine .
:DLRLine
    a trains:Line ;
    skos:prefLabel &quot;Docklands Light Railway&quot; ;
    trains:operatedBy :DLR .
:GWR
    a trains:Line ;
    skos:prefLabel &quot;Great Western Railway&quot; ;
    trains:operatedBy :NationalRail .
:LNER
    a trains:Line ;
    skos:prefLabel &quot;London North Eastern Railway&quot; ;
    trains:operatedBy :NationalRail .
:Southern
    a trains:Line ;
    skos:prefLabel &quot;Southern&quot; ;
    trains:operatedBy :NationalRail .
# Stations
:OxfordCircus
    a trains:Station ;
    skos:prefLabel &quot;Oxford Circus&quot; ;
    trains:inZone :Zone1 .
:BondStreet
    a trains:Station ;
    skos:prefLabel &quot;Bond Street&quot; ;
    trains:inZone :Zone1 .
:LiverpoolStreet
    a trains:Station ;
    skos:prefLabel &quot;Liverpool Street&quot; ;
    trains:inZone :Zone1 .
:StratfordStation
    a trains:Station ;
    skos:prefLabel &quot;Stratford&quot; ;
    trains:inZone :Zone3 .
:CanaryWharf
    a trains:Station ;
    skos:prefLabel &quot;Canary Wharf&quot; ;
    trains:inZone :Zone2 .
:KingsCross
    a trains:Station ;
    skos:prefLabel &quot;King&#x27;s Cross St. Pancras&quot; ;
    trains:inZone :Zone1 .
:BankStation
    a trains:Station ;
    skos:prefLabel &quot;Bank&quot; ;
    trains:inZone :Zone1 .
:WaterlooStation
    a trains:Station ;
    skos:prefLabel &quot;Waterloo&quot; ;
    trains:inZone :Zone1 .
:BrixtonStation
    a trains:Station ;
    skos:prefLabel &quot;Brixton&quot; ;
    trains:inZone :Zone2 .
:EalingBroadway
    a trains:Station ;
    skos:prefLabel &quot;Ealing Broadway&quot; ;
    trains:inZone :Zone3 .
:Paddington
    a trains:Station ;
    skos:prefLabel &quot;Paddington&quot; ;
    trains:inZone :Zone1 .
# :Reading
#     a trains:Station ;
#     skos:prefLabel &quot;Reading&quot; .
# :BristolTempleMeads
#     a trains:Station ;
#     skos:prefLabel &quot;Bristol Temple Meads&quot; .
# :York
#     a trains:Station ;
#     skos:prefLabel &quot;York&quot; .
# :EdinburghWaverley
#     a trains:Station ;
#     skos:prefLabel &quot;Edinburgh Waverley&quot; .
# :LondonBridge
#     a trains:Station ;
#     skos:prefLabel &quot;London Bridge&quot; ;
#     trains:inZone :Zone1 .
# :GatwickAirport
#     a trains:Station ;
#     skos:prefLabel &quot;Gatwick Airport&quot; .
# :Brighton
#     a trains:Station ;
#     skos:prefLabel &quot;Brighton&quot; .
:TowerGateway
    a trains:Station ;
    skos:prefLabel &quot;Tower Gateway&quot; ;
    trains:inZone :Zone1 .
:Shadwell
    a trains:Station ;
    skos:prefLabel &quot;Shadwell&quot; ;
    trains:inZone :Zone2 .
:Limehouse
    a trains:Station ;
    skos:prefLabel &quot;Limehouse&quot; ;
    trains:inZone :Zone2 .
:Poplar
    a trains:Station ;
    skos:prefLabel &quot;Poplar&quot; ;
    trains:inZone :Zone2 .
:Westferry
    a trains:Station ;
    skos:prefLabel &quot;Westferry&quot; ;
    trains:inZone :Zone2 .
:HeronQuays
    a trains:Station ;
    skos:prefLabel &quot;Heron Quays&quot; ;
    trains:inZone :Zone2 .
# Line-station relationships
:CentralLine
    trains:hasStation :OxfordCircus ;
    trains:hasStation :BondStreet ;
    trains:hasStation :BankStation ;
    trains:hasStation :LiverpoolStreet ;
    trains:hasStation :EalingBroadway .
:JubileeLine
    trains:hasStation :BondStreet ;
    trains:hasStation :WaterlooStation ;
    trains:hasStation :CanaryWharf ;
    trains:hasStation :StratfordStation .
:NorthernLine
    trains:hasStation :KingsCross ;
    trains:hasStation :BankStation ;
    trains:hasStation :WaterlooStation ;
    trains:hasStation :BrixtonStation .
:VictoriaLine
    trains:hasStation :OxfordCircus ;
    trains:hasStation :KingsCross ;
    trains:hasStation :WaterlooStation ;
    trains:hasStation :BrixtonStation .
:ElizabethLineSvc
    trains:hasStation :BondStreet ;
    trains:hasStation :LiverpoolStreet ;
    trains:hasStation :CanaryWharf ;
    trains:hasStation :StratfordStation .
:GWR
    trains:hasStation :Paddington ;
    trains:hasStation :Reading ;
    trains:hasStation :BristolTempleMeads .
:LNER
    trains:hasStation :KingsCross ;
    trains:hasStation :York ;
    trains:hasStation :EdinburghWaverley .
:Southern
    trains:hasStation :LondonBridge ;
    trains:hasStation :GatwickAirport ;
    trains:hasStation :Brighton .
:DLRLine
    trains:hasStation :BankStation ;
    trains:hasStation :TowerGateway ;
    trains:hasStation :Shadwell ;
    trains:hasStation :Limehouse ;
    trains:hasStation :Westferry ;
    trains:hasStation :Poplar ;
    trains:hasStation :HeronQuays ;
    trains:hasStation :CanaryWharf ;
    trains:hasStation :StratfordStation .
</pre></details></td></tr>
<tr><th>ontology file(s)</th><td>—</td></tr>
<tr><th>ontology conforms</th><td>—</td></tr>
<tr><th>SHACL file(s)</th><td><details><summary>/Users/pelolson-sp/mustrd/new_feature_shacl/train_shapes.ttl</summary><pre>@prefix sh:     &lt;http://www.w3.org/ns/shacl#&gt; .
@prefix trains: &lt;https://example.org/trains-Ontology#&gt; .
@prefix xsd:    &lt;http://www.w3.org/2001/XMLSchema#&gt; .
trains:StationShape
    a sh:NodeShape ;
    sh:targetClass trains:Station ;
    sh:property [
        sh:path     [ sh:inversePath trains:hasStation ] ;
        sh:class    trains:Line ;
        sh:minCount 1 ;
        sh:message  &quot;A Station must be the object of at least one trains:hasStation triple whose subject is a trains:Line.&quot; ;
    ] ;
    sh:property [
        sh:path      trains:inZone ;
        sh:class  trains:Zone ;
        sh:minCount  1 ;
        sh:message   &quot;A Station must have at least one trains:inZone value of type trains:Zone.&quot; ;
    ] .
</pre></details></td></tr>
<tr><th>SHACL conforms</th><td>✓</td></tr>
</table>
</details></td>
</tr>
</tbody>
</table>
</div>
</details>
</div>
</details>