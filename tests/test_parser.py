from paster.parser import parse_whatsapp_text


def test_parser_extracts_assignment_and_completion():
    text = """
1. SFKL4421 Nyok Mawir 789022235 02-S-FKLN-06
DIANI ROAD NewActivation Road name: Diana Road

GPON INSTALL
"Date"28/4/2026
Account:SFKL7233
ADDRESS: Delamere Flats
client name: Tamara Sikipa
client contact: 0721272362
fiber home mac:FHTTC1BD2AC4
Signal At FAT: -33.40
Signal At ATB: -34.53
Materials indoor drop cable: 37m
ATB : 1
PATCH CORD : 1 BG
fat need to be optimized
@~Lawrence Lagat
""".strip()

    result = parse_whatsapp_text(text)

    assert len(result.assignments) == 1
    assert result.assignments[0].account == "SFKL4421"
    assert result.assignments[0].contact == "0789022235"
    assert result.assignments[0].status is None

    assert len(result.completions) == 1
    completion = result.completions[0]
    assert completion.account == "SFKL7233"
    assert completion.client_name == "Tamara Sikipa"
    assert completion.serial_number == "FHTTC1BD2AC4"
    assert completion.indoor_cable == "37m"
    assert completion.power_level == 34.53
    assert completion.power_fat == 33.4
    assert completion.remarks == "Connected - needs optimization"

    assert result.summary_counts["Assigned Tickets"] == 1
    assert result.summary_counts["Tickets done"] == 1


def test_parser_extracts_all_assignment_lines_without_duplicates():
    text = """
Team please see below TEAM DISTRIBUTION FOR 29/4/2026

*LANG'ATA*
LAISA
NELSON

860 | 2026-04-29 08:25:41
@213267255423081

SFKL10583\tRita Mung'ohe\t704777265\tLANG'ATA ROAD\tAssigned\tClient Available
SFKL17306\tCarolyne Karanja\t723841358\tLANG'ATA ROAD\tAssigned\tClient Available
SFKL11915\tRajan Suthar\t0103493969 LANG'ATA LINK ROAD NewActivation 05-S-FPHM-04\tGopi apartment

860 | 2026-04-29 08:26:16
@231782691696660
SFKL14503\tRabadiya Jitendra\t703940113\tLANG'ATA LINK ROAD
SFKL17356\tKamau Njonjo\t710537836\tLANG'ATA ROAD\tOnhold\t28th April: Client available tomorrow 29th April from 10am.
SFKL10583\tRita Mung'ohe\t704777265\tLANG'ATA ROAD\tAssigned\tClient Available
""".strip()

    result = parse_whatsapp_text(text)

    assert len(result.assignments) == 5
    accounts = {item.account for item in result.assignments}
    assert accounts == {"SFKL10583", "SFKL17306", "SFKL11915", "SFKL14503", "SFKL17356"}

    by_account = {item.account: item for item in result.assignments}
    assert by_account["SFKL11915"].contact == "0103493969"
    assert by_account["SFKL11915"].route_code == "05-S-FPHM-04"
    assert by_account["SFKL11915"].location == "LANG'ATA LINK ROAD"
    assert by_account["SFKL11915"].tech == "@213267255423081"
    assert by_account["SFKL11915"].status == "NewActivation"
    assert by_account["SFKL11915"].remarks == "Gopi apartment"
    assert by_account["SFKL10583"].location == "LANG'ATA ROAD"
    assert by_account["SFKL10583"].status == "Assigned"
    assert by_account["SFKL10583"].remarks == "Client Available"
    assert by_account["SFKL17356"].status == "Onhold"
    assert by_account["SFKL17356"].remarks == "28th April: Client available tomorrow 29th April from 10am."
    assert result.summary_counts["Assigned Tickets"] == 5


def test_parser_extracts_assignment_status_and_inline_remarks():
    text = """
SFKL3042\tRahma Mohammed\t710893567\tLANG'ATA ROAD-Share coordinates of this Not fiber ready
SFKL17399\tArnold Kyenze\t721422338\tLANG'ATA ROAD\tAssigned\tScheduled tomorrow
""".strip()

    result = parse_whatsapp_text(text)

    assert len(result.assignments) == 2
    by_account = {item.account: item for item in result.assignments}
    assert by_account["SFKL3042"].location == "LANG'ATA ROAD"
    assert by_account["SFKL3042"].status == "Not fiber ready"
    assert by_account["SFKL3042"].remarks == "Share coordinates of this"
    assert by_account["SFKL17399"].status == "Assigned"
    assert by_account["SFKL17399"].remarks == "Scheduled tomorrow"


def test_parser_extracts_tabbed_route_location_status_and_remarks():
    text = """
SFKL13441\tHilda Wangari\t721766422\t02-S-FKLN-01\tKILIMANI ROAD\tNewActivation\tAnfield Apartment: client available Wednesday
SFKL15111\tBenjamin Karani\t721990195\t02-S-FKLN-13\tKIBERA STATION ROAD\tNewActivation\telimu court
""".strip()

    result = parse_whatsapp_text(text)

    assert len(result.assignments) == 2
    by_account = {item.account: item for item in result.assignments}
    assert by_account["SFKL13441"].route_code == "02-S-FKLN-01"
    assert by_account["SFKL13441"].location == "KILIMANI ROAD"
    assert by_account["SFKL13441"].status == "NewActivation"
    assert by_account["SFKL13441"].remarks == "Anfield Apartment: client available Wednesday"
    assert by_account["SFKL15111"].route_code == "02-S-FKLN-13"
    assert by_account["SFKL15111"].location == "KIBERA STATION ROAD"
    assert by_account["SFKL15111"].status == "NewActivation"
    assert by_account["SFKL15111"].remarks == "elimu court"


def test_parser_extracts_field_activity_reports_and_team_count():
    text = """
Contractor:Comcraft
Location:kileleshwa
Scipe:FTTH
POB:3
TOPIC: severe weather

Contractor:Comcraft
Location:kileleshwa
Scipe:FTTH
POB:3
TOPIC: severe weather
""".strip()

    result = parse_whatsapp_text(text)

    assert len(result.field_activity_reports) == 1
    report = result.field_activity_reports[0]
    assert report.contractor == "Comcraft"
    assert report.location == "kileleshwa"
    assert report.scope == "FTTH"
    assert report.pob == 3
    assert report.topic == "severe weather"
    assert result.summary_counts["Teams Available"] == 1
    assert result.summary_counts["Tickets Rescheduled due to weather"] >= 1


def test_parser_extracts_completion_with_whatsapp_label_variants():
    text = """
GPON INSTALL

*Date*28/4/2026
Account:Sfkl13976
ADDRESS: Wood Avenue Park
house type:MDU
Client name; Florence
Client contact: 0723569556
Fiber home Mac:FHTTC1B96480
Signal At FAT:   -15.02
Signal At ATB:  - 15.93
Materials  out door drop cable: 55m
Sleeves: 2

Trunking:0
ATB : 1
PATCH CORD :  1 BG

Username:  KUREMA 5G
Password:   0987654321
Client present during installation. Florence
""".strip()

    result = parse_whatsapp_text(text)

    assert len(result.completions) == 1
    completion = result.completions[0]
    assert completion.account == "SFKL13976"
    assert completion.client_name == "Florence"
    assert completion.location == "Wood Avenue Park"
    assert completion.contact == "0723569556"
    assert completion.serial_number == "FHTTC1B96480"
    assert completion.close_datetime == "28/4/2026"
    assert completion.outdoor_cable == "55m"
    assert completion.atb == 1
    assert completion.patch == 1
    assert completion.power_fat == 15.02
    assert completion.power_level == 15.93


def test_parser_extracts_completion_without_explicit_gpon_header():
    text = """
*Date*29/4/2026
*Account*:SFKL 17396
*ADDRESS*Kileleshwa
suguta road
*house type*: MDU
Client name; Abdimajid Mohamed
contact:0726696958
Fiber home  FHTTC1BD0AA6
CanSignal At FAT:19
Signal At atb: 20
*Materials*
Indoor  drop cable: 41m
Sleeves: 2
Trunking:0
ATB : 1v
PATCH CORD :  1 B
Username: HODHAN
Password: HODAN2026
Client present during installation: Abdimajid
""".strip()

    result = parse_whatsapp_text(text)

    assert len(result.completions) == 1
    completion = result.completions[0]
    assert completion.account == "SFKL17396"
    assert completion.client_name == "Abdimajid Mohamed"
    assert completion.contact == "0726696958"
    assert completion.serial_number == "FHTTC1BD0AA6"
    assert completion.indoor_cable == "41m"
    assert completion.atb == 1
    assert completion.patch == 1


def test_parser_ignores_inventory_assignment_requests_as_tickets():
    text = """
Levi | 2026-04-29 08:12:01
SFKL17346 *assign inventory*

Eng. Rono | 2026-04-29 09:13:43
Attach inventory

Levi | 2026-04-29 10:14:39
SFKL17448 ✅Link is up and pushing traffic
""".strip()

    result = parse_whatsapp_text(text)

    assert len(result.assignments) == 0
    assert len(result.completions) == 0


def test_parser_ignores_bad_power_optimize_updates_as_tickets():
    text = """
Levi | 2026-04-29 10:18:11
SFKL17448 *Bad power, optimize*
""".strip()

    result = parse_whatsapp_text(text)

    assert len(result.assignments) == 0
    assert len(result.completions) == 0


def test_parser_applies_bad_power_optimize_updates_to_matching_completion_remarks():
    text = """
GPON INSTALL
Date 29/4/2026
Account:SFKL17448
Fiber home Mac:FHTTC1B95D5D
Signal At FAT: 15.12
Signal At ATB: 16.18
ATB : 1
PATCH CORD : 1

Levi | 2026-04-29 10:18:11
SFKL17448 *Bad power, optimize*
""".strip()

    result = parse_whatsapp_text(text)

    assert len(result.completions) == 1
    assert result.completions[0].account == "SFKL17448"
    assert result.completions[0].remarks == "Bad power, optimize"


def test_parser_backfills_completion_details_from_matching_assignment():
    text = """
@231782691696660
SFKL17448\tMerkn Kumlachew\t795287129\tKINDARUMA ROAD\tAssigned\tNine Planet Apartments

GPON INSTALL
Date 29/4/2026
Account:SFKL17448
Fiber home Mac:FHTTC1B95D5D
Signal At FAT: 15.12
Signal At ATB: 16.18
ATB : 1
PATCH CORD : 1
""".strip()

    result = parse_whatsapp_text(text)

    assert len(result.completions) == 1
    completion = result.completions[0]
    assert completion.account == "SFKL17448"
    assert completion.client_name == "Merkn Kumlachew"
    assert completion.contact == "0795287129"
    assert completion.location == "Nine Planet Apartments"
    assert completion.tech == "@231782691696660"


def test_parser_does_not_create_duplicate_completion_from_account_only_follow_up():
    text = """
@231782691696660
SFKL17482 Caroline Nyambura Kiragu 726469455 KITENGELA ROAD 05-S-FLAG-08 Park 2 Estate

Levi | 2026-04-29 17:31:40
ACCOUNT: SFKL17482

*Date*:29/4/2026
*Account*:SFKL17482
*ADDRESS*: park 2
*house type*: sdu
Client name:Caron Nyambura
Client contact:0726469455
Mac:FHTTC1B95D41
Signal At FAT :20.14
Signal at ATB :22.07
*Materials*
Indoor drop cable 69m
ATB : 1
PATCH CORD : 1
""".strip()

    result = parse_whatsapp_text(text)

    matching = [item for item in result.completions if item.account == "SFKL17482"]
    assert len(matching) == 1
    assert matching[0].serial_number == "FHTTC1B95D41"
    assert matching[0].power_level == 22.07
