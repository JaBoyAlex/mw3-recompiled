#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Check reference plans/evidence declarations; never launch or certify gameplay."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODES = {"campaign", "spec_ops_missions", "survival", "multiplayer_local",
         "multiplayer_online", "multiplayer_system_link", "shared"}
AREAS = {"identity", "mission", "map", "difficulty", "checkpoint", "controller",
         "save", "players", "region", "dlc", "gameplay", "pause", "presentation"}
STATUSES = {"PASS", "FAIL", "SKIP", "NOT_RUN"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names):
    require(isinstance(value, dict) and set(value) == set(names.split()), "unexpected/missing fields")


def text(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= 2000


def digest(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def unique(rows, key="id"):
    require(isinstance(rows, list) and 0 < len(rows) <= 1000, "bounded nonempty records required")
    result = {}
    for row in rows:
        require(isinstance(row, dict) and text(row.get(key)), "record identifier required")
        require(row[key] not in result, "duplicate identifier")
        result[row[key]] = row
    return result


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def load(path):
    require(stat.S_ISREG(Path(path).stat().st_mode), "regular JSON file required")
    with Path(path).open("rb") as stream:
        data = stream.read(2 * 1024 * 1024 + 1)
    require(len(data) <= 2 * 1024 * 1024, "JSON byte budget exceeded")
    def invalid_constant(value):
        raise ValueError("nonfinite JSON number")
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid_constant)


def baseline():
    manifest = load(ROOT / "config/titles/mw3-xbox360-rev1.json")
    return dict(manifest_id=manifest["id"], iso_sha256=manifest["iso"]["sha256"],
                executable_sha256={r["name"]: r["sha256"] for r in manifest["executables"]},
                title_update="not_supplied", dlc="not_supplied")


def value_matches(value, kind):
    return ((kind == "count" and type(value) is int and 1 <= value <= 64)
            or (kind == "boolean" and type(value) is bool) or (kind == "text" and text(value)))


def validate_catalog(data):
    fields(data, "schema_version task baseline sources facts inventories cases")
    require(type(data["schema_version"]) is int and data["schema_version"] == 1, "unknown schema")
    require(data["task"] == "MW3-004" and data["baseline"] == baseline(), "wrong baseline/build identity")
    sources = unique(data["sources"])
    for row in sources.values():
        fields(row, "id kind location sha256 page_count")
        require(row["kind"] in {"manual", "repo_manifest", "project_requirement", "console_observation"},
                "unknown source evidence class")
        require(text(row["location"]) and digest(row["sha256"]), "source location/hash required")
        if row["kind"] == "manual":
            require(type(row["page_count"]) is int and 0 < row["page_count"] <= 1000, "manual pages required")
        else:
            require(row["page_count"] is None, "page count only belongs to a manual")
        if row["kind"] in {"repo_manifest", "project_requirement"}:
            rel = PurePosixPath(row["location"])
            require(not rel.is_absolute() and ".." not in rel.parts and "\\" not in row["location"], "unsafe source path")
            require(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == row["sha256"], "changed source pin")
    facts = unique(data["facts"])
    for row in facts.values():
        fields(row, "id mode kind value basis source pdf_page reason")
        require(row["mode"] in MODES | {"special_ops", "survival_extension"}, "unknown fact mode")
        require(row["kind"] in {"count", "boolean", "text"}, "unknown value kind")
        require(row["basis"] in {"manual", "console", "unobserved", "owner_extension"}, "unknown fact basis")
        if row["basis"] == "unobserved":
            require(row["value"] is None and row["source"] is None and row["pdf_page"] is None
                    and text(row["reason"]), "unknown fact cannot acquire a value or lose its reason")
        else:
            require(value_matches(row["value"], row["kind"]), "wrong fact value type")
            require(row["source"] in sources, "missing fact source")
            source = sources[row["source"]]
            expected = {"manual": "manual", "console": "console_observation", "owner_extension": "project_requirement"}
            require(source["kind"] == expected[row["basis"]], "source class cannot establish this fact")
            if row["basis"] == "manual":
                require(type(row["pdf_page"]) is int and 0 <= row["pdf_page"] < source["page_count"], "bad PDF page")
            else:
                require(row["pdf_page"] is None, "unexpected PDF page")
            require(row["reason"] == "", "known fact has an unknown reason")
    inventories = unique(data["inventories"])
    for row in inventories.values():
        fields(row, "id mode required state items reason")
        require(row["mode"] in MODES and type(row["required"]) is bool, "bad inventory scope")
        require(row["state"] in {"unknown", "not_supplied", "complete"}, "bad inventory state")
        require(isinstance(row["items"], list) and len(row["items"]) <= 10000
                and all(text(v) for v in row["items"]) and len(set(row["items"])) == len(row["items"]), "bad inventory items")
        require((row["state"] == "complete" and row["items"] and row["reason"] == "")
                or (row["state"] != "complete" and not row["items"] and text(row["reason"])),
                "unknown/empty inventory cannot establish completed coverage")
    cases = unique(data["cases"])
    for row in cases.values():
        fields(row, "id mode area scope required procedure checks facts inventories prerequisites status reason")
        require(re.fullmatch(r"REF-[A-Z0-9-]+", row["id"]) is not None, "bad case ID")
        require(row["mode"] in MODES | {"survival_extension"} and row["area"] in AREAS, "bad case mode/area")
        require(row["scope"] in {"retail", "extension"} and type(row["required"]) is bool, "bad case scope")
        require(row["status"] == "NOT_RUN" and text(row["reason"]), "catalog is a plan, not executed results")
        for name in ("procedure", "checks", "prerequisites"):
            require(isinstance(row[name], list) and 0 < len(row[name]) <= 32 and all(text(v) for v in row[name]), "case contract missing")
        require(len(set(row["checks"])) == len(row["checks"]), "duplicate check")
        for name, known in (("facts", facts), ("inventories", inventories)):
            require(isinstance(row[name], list) and len(set(row[name])) == len(row[name])
                    and all(key in known for key in row[name]), "dangling case dependency")
        if row["scope"] == "retail":
            require(row["mode"] != "survival_extension"
                    and all(facts[key]["basis"] != "owner_extension" for key in row["facts"]), "extension cannot become retail parity")
        else:
            require(not row["required"], "extension cannot satisfy the retail reference gate")
    require({r["mode"] for r in cases.values() if r["scope"] == "retail"} == MODES, "missing baseline mode")
    require({r["mode"] for r in cases.values() if r["scope"] == "retail" and r["required"]} == MODES,
            "required baseline mode cannot be silently omitted")
    require(AREAS <= {r["area"] for r in cases.values()}, "missing coverage area")
    return sources, facts, inventories, cases


def catalog_hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def template(data):
    validate_catalog(data)
    return dict(schema_version=1, catalog_sha256=catalog_hash(data), baseline=data["baseline"],
                synthetic=False, origin="unobserved", console=None,
                cases=[dict(case_id=r["id"], status="NOT_RUN", reason=r["reason"],
                            checks={}, observed={}, artifacts=[]) for r in data["cases"]])


def check_artifact(root, row):
    fields(row, "path sha256")
    require(text(row["path"]) and digest(row["sha256"]), "artifact identity required")
    name = PurePosixPath(row["path"])
    require(not name.is_absolute() and not any(c in row["path"] for c in "\\:\x00")
            and ".." not in name.parts and name.name and not row["path"].endswith("/"), "unsafe artifact path")
    path = Path(root).absolute()
    for ancestor in reversed((path, *path.parents)):
        info = ancestor.lstat()
        require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
                and not getattr(info, "st_file_attributes", 0) & 0x400, "redirected artifact root")
    for part in name.parts:
        path = path / part
        info = path.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "redirected artifact")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= 64 * 1024**3,
            "regular bounded artifact required")
    digest_value = hashlib.sha256()
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require((opened.st_dev, opened.st_ino, opened.st_size) == (before.st_dev, before.st_ino, before.st_size),
                "artifact changed at open")
        for offset in range(0, before.st_size, 1024 * 1024):
            block = stream.read(min(1024 * 1024, before.st_size - offset))
            require(len(block) == min(1024 * 1024, before.st_size - offset), "truncated artifact")
            digest_value.update(block)
    after = path.lstat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "artifact changed while reading")
    require(digest_value.hexdigest() == row["sha256"], "artifact hash mismatch")


def validate_submission(data, submission, artifact_root):
    _, facts, inventories, cases = validate_catalog(data)
    fields(submission, "schema_version catalog_sha256 baseline synthetic origin console cases")
    require(type(submission["schema_version"]) is int and submission["schema_version"] == 1, "unknown result schema")
    require(submission["catalog_sha256"] == catalog_hash(data) and submission["baseline"] == data["baseline"],
            "changed catalog or build/update/DLC context")
    require(type(submission["synthetic"]) is bool, "explicit synthetic boolean required")
    require(submission["origin"] in {"unobserved", "owned_console", "synthetic"}, "not a console-reference source")
    require(submission["synthetic"] == (submission["origin"] == "synthetic"), "contradictory synthetic origin")
    results = unique(submission["cases"], "case_id")
    require(set(results) == set(cases), "missing/extra case results")
    counts = dict.fromkeys(sorted(STATUSES), 0)
    for ident, row in results.items():
        plan = cases[ident]
        fields(row, "case_id status reason checks observed artifacts")
        require(row["status"] in STATUSES, "unknown result status")
        require(isinstance(row["checks"], dict) and set(row["checks"]) <= set(plan["checks"])
                and all(type(v) is bool for v in row["checks"].values()), "invalid check results")
        require(isinstance(row["observed"], dict) and set(row["observed"]) <= set(plan["facts"]), "unexpected observation")
        require(isinstance(row["artifacts"], list) and len(row["artifacts"]) <= 32, "artifact budget exceeded")
        if row["status"] in {"PASS", "FAIL"}:
            require(submission["origin"] != "unobserved", "unobserved work cannot pass or fail")
            console = submission["console"]
            fields(console, "platform model system_version title_update_state dlc_state profile_id capture_tool")
            require(console["platform"] == "xbox360" and all(text(v) for v in console.values()), "console identity required")
            require(console["title_update_state"] == "confirmed_absent" and console["dlc_state"] == "baseline_only",
                    "unverified update/DLC cannot inherit baseline identity")
            require(row["artifacts"] and artifact_root is not None, "executed cases require retained evidence")
        if row["status"] == "PASS":
            require(set(row["checks"]) == set(plan["checks"]) and all(row["checks"].values()), "missing/failed assertion")
            require(set(row["observed"]) == set(plan["facts"]), "missing observation")
            require(all(inventories[k]["state"] == "complete" for k in plan["inventories"]), "unresolved case inventory")
            for key, value in row["observed"].items():
                require(facts[key]["value"] is not None and value_matches(value, facts[key]["kind"])
                        and type(value) is type(facts[key]["value"]) and value == facts[key]["value"],
                        "unknown or mismatched reference expectation")
        else:
            require(text(row["reason"]), "nonpassing result needs an explicit reason")
        for artifact in row["artifacts"]:
            require(artifact_root is not None, "artifact root required")
            check_artifact(artifact_root, artifact)
        counts[row["status"]] += 1
    complete = (not submission["synthetic"] and submission["origin"] == "owned_console"
                and all(r["status"] == "PASS" for key, r in results.items() if cases[key]["required"])
                and all(r["state"] == "complete" for r in inventories.values() if r["required"])
                and all(r["basis"] != "unobserved" for r in facts.values() if r["mode"] != "survival_extension"))
    return dict(counts=counts, console_submission_complete=complete, synthetic=submission["synthetic"],
                semantic_review_required=True, gameplay_certified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=HERE / "catalog.json")
    parser.add_argument("--results", type=Path)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--template", type=Path, help="exclusively write an unobserved private results template")
    parser.add_argument("--require-console", action="store_true", help="exit 2 until full declared console coverage exists")
    args = parser.parse_args()
    try:
        data = load(args.catalog)
        _, facts, inventories, cases = validate_catalog(data)
        if args.template:
            with args.template.open("x", encoding="utf-8") as stream:
                json.dump(template(data), stream, indent=2)
                stream.write("\n")
        report = dict(catalog_valid=True, cases=len(cases), unknown_facts=sum(r["basis"] == "unobserved" for r in facts.values()),
                      unresolved_inventories=sum(r["state"] != "complete" for r in inventories.values() if r["required"]),
                      console_submission_complete=False, gameplay_certified=False)
        if args.results:
            report.update(validate_submission(data, load(args.results), args.artifacts))
        print(json.dumps(report, sort_keys=True))
        return 2 if args.require_console and not report["console_submission_complete"] else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"reference validation failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
