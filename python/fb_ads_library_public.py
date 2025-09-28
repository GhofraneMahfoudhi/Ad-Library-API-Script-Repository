#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import sys

from fb_ads_library_api import FbAdsLibraryTraversal
from fb_ads_library_api_operators import get_operators, save_to_csv
from fb_ads_library_api_utils import get_country_code, is_valid_fields


def get_parser():
    parser = argparse.ArgumentParser(
        description="The Facebook Ads Library API CLI Utility"
    )
    parser.add_argument("-s", "--search-term", help="The term you want to search for")
    parser.add_argument(
        "-c",
        "--country",
        help="Comma-separated country code (no spaces)",
        required=True,
        type=validate_country_param,
    )
    parser.add_argument(
        "--search-page-ids", help="The specific Facebook Page you want to search"
    )
    parser.add_argument(
        "--retry-limit",
        type=int,
        help="When an error occurs, the script will abort if it fails to get the same batch this amount of times",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    actions = ",".join(get_operators().keys())
    parser.add_argument(
        "action",
        nargs='?',
        help="Action to take on the ads, possible values: %s" % actions,
    )
    parser.add_argument(
        "args", nargs=argparse.REMAINDER, help="The parameter for the specific action"
    )
    parser.add_argument(
        "-f",
        "--fields",
        help=(
            "Comma-separated list of fields to retrieve for each ad. "
            "See documentation for supported fields."
        ),
        type=validate_fields_param,
    )
    parser.add_argument(
        "--print-public-url",
        help="Print the Ads Library public search URL for the given search and country",
        action="store_true",
    )
    parser.add_argument(
        "--open-public-url",
        help="Open the Ads Library public search URL in the default browser",
        action="store_true",
    )
    parser.add_argument(
        "--use-public-fetch",
        help="Use a headless browser to fetch Ads Library data from the public page (requires Playwright)",
        action="store_true",
    )
    return parser


def validate_country_param(country_input):
    if not country_input:
        return ""
    country_list = list(filter(lambda x: x.strip(), country_input.split(",")))
    if not country_list:
        raise argparse.ArgumentTypeError("Country cannot be empty")
    valid_country_codes = list(map(lambda x: get_country_code(x), country_list))
    invalid_inputs = {
        key: value
        for (key, value) in zip(country_list, valid_country_codes)
        if value is None
    }

    if invalid_inputs:
        raise argparse.ArgumentTypeError(
            "Invalid/unsupported country code: %s" % (",".join(invalid_inputs.keys()))
        )
    else:
        return ",".join(valid_country_codes)


def validate_fields_param(fields_input):
    if not fields_input:
        return False
    fields_list = list(
        filter(lambda x: x, map(lambda x: x.strip(), fields_input.split(",")))
    )
    if not fields_list:
        raise argparse.ArgumentTypeError("Fields cannot be empty")
    invalid_fields = list(filter(lambda x: not is_valid_fields(x), fields_list))
    if not invalid_fields:
        return ",".join(fields_list)
    else:
        raise argparse.ArgumentTypeError(
            "Unsupported fields: %s" % (",".join(invalid_fields))
        )


def main():
    parser = get_parser()
    opts = parser.parse_args()

    if not opts.search_term and not opts.search_page_ids:
        print("At least one must be set: --search-term, --search-page-ids")
        sys.exit(1)

    if not opts.search_term:
        search_term = "."
    else:
        search_term = opts.search_term
    api = FbAdsLibraryTraversal(
         search_term, opts.country
    )
    # If user only wants the public URL, print/open and exit before fetching
    if getattr(opts, "print_public_url", False) or getattr(opts, "open_public_url", False):
        public_url = api.get_public_search_url()
        if getattr(opts, "print_public_url", False):
            print(public_url)
        if getattr(opts, "open_public_url", False):
            try:
                import webbrowser

                webbrowser.open(public_url)
            except Exception as e:
                print(f"Failed to open browser: {e}")
        sys.exit(0)
    # For other operations, an action is required
    if not opts.action:
        print("'action' is required unless --print-public-url or --open-public-url is used")
        parser.print_help()
        sys.exit(1)

    # Choose fetch method: async endpoint (default) or public-page headless fetch
    if getattr(opts, "use_public_fetch", False):
        try:
            generator_ad_archives = api.generate_ad_archives_from_public_page()
        except RuntimeError as e:
            print(e)
            sys.exit(1)
    else:
        generator_ad_archives = api.generate_ad_archives()
    if opts.action in get_operators():
        if opts.action == "save_to_csv":
            if not opts.fields:
                print("The --fields parameter is required for save_to_csv action")
                sys.exit(1)
            save_to_csv(generator_ad_archives, opts.args, opts.fields, is_verbose=opts.verbose)
        else:
            get_operators()[opts.action](
                generator_ad_archives, opts.args, is_verbose=opts.verbose
            )
    else:
        print("Invalid 'action' value: %s" % opts.action)
        sys.exit(1)


if __name__ == "__main__":
    main()
