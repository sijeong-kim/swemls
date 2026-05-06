from datetime import datetime
import re


MLLP_START_OF_BLOCK = 0x0B
MLLP_END_OF_BLOCK = 0x1C
MLLP_CARRIAGE_RETURN = 0x0D


def create_mllp_ack():
    current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
    return (
        bytes([MLLP_START_OF_BLOCK])
        + f"MSH|^~\\&|||||{current_datetime}||ACK|||2.5\r".encode('ascii')
        + b"MSA|AA\r"
        + bytes([MLLP_END_OF_BLOCK, MLLP_CARRIAGE_RETURN])
    )


def parse_mllp_frames(data):
    messages = []
    while True:
        start = data.find(bytes([MLLP_START_OF_BLOCK]))
        if start == -1:
            break
        end = data.find(bytes([MLLP_END_OF_BLOCK]), start)
        if end == -1 or end + 1 >= len(data) or data[end + 1] != MLLP_CARRIAGE_RETURN:
            break
        messages.append(data[start + 1 : end])
        data = data[end + 2 :]
    return messages, data


def normalize_timestamp(timestamp):
    if len(timestamp) == 12:
        timestamp += "00"

    return timestamp


def parse_one_raw_hl7_message(hl7_message):
    hl7_message = hl7_message.decode("utf-8").strip().split("\r")
    parsed_results = dict()

    for segment in hl7_message:
        fields = segment.split("|")
        segment_type = fields[0]

        if segment_type == "MSH":  # Message Header
            field_seperator = f"[{re.escape(fields[1])}]"  # '^~\\&'
            message_type = " ".join(re.split(field_seperator, fields[8]))

            parsed_results["message_type"] = message_type
        else:
            if message_type == "ORU R01":
            # LIMS system message: receiving the result of a creatinine blood test result
                match segment_type:
                    case "PID":
                        parsed_results["mrn"] = fields[3]
                    case "OBR":
                        parsed_results["blood_test_time"] = datetime.strptime(
                            normalize_timestamp(fields[7]), "%Y%m%d%H%M%S"
                        )
                    case "OBX":
                        (
                            parsed_results["blood_test_type"],
                            parsed_results["blood_test_result"],
                        ) = fields[3], float(fields[5])
                    case _:
                        print("There is no match")

            elif message_type == "ADT A01":
                # PAS system message: admitting a patient to hospital
                if segment_type == "PID":
                    (
                        parsed_results["mrn"],
                        parsed_results["name"],
                        parsed_results["dob"],
                        parsed_results["sex"],
                    ) = (
                        fields[3],
                        fields[5],
                        datetime.strptime(fields[7], "%Y%m%d"),
                        fields[8],
                    )

            elif message_type == "ADT A03":
                # PAS system message: discharing a patient from hospital
                if segment_type == "PID":
                    parsed_results["mrn"] = fields[3]

    return parsed_results
