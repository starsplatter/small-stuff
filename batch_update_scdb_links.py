#!/usr/bin/python

import csv
import sys

# Only works with MSS table. Update for each table.

TABLE = 'SPEC_MAN_MANUSCRIPTS_MAN'
ID = 'id_man'
IDENTIFIER = 'coll_man'
LINK = 'link_guide'

# SPEC_MAN_MANUSCRIPTS_MAN, id_man, coll_man/link_photos
# SPEC_ORAL_HISTORY_SOH, id_soh, coll_number_soh, link_digital_soh
# SPEC_PC_PHOTOCOLL_PHO, id_pho, coll_number_pho/link_photos_pho
# SPEC_UNLV_ARCHIVES_UAR, id_uar, link_guide_uar


if __name__ == '__main__':

    # Ensure we have the two arguments
    if not len(sys.argv) > 2:
        print 'Please provide both the archivesspace export and scdb export'
        exit();

    # load up an identifier associative array storing arks for guides
    identifier_ark = {}
    with open(sys.argv[1]) as csvfile:
        reader = csv.DictReader(csvfile, delimiter='\t')
        for row in reader:
            identifier_ark[row['identifier']] = row['ead_location']

    # Run through the DB entries and create update statements
    update_sql = ''
    with open(sys.argv[2]) as csvfile:
        reader = csv.DictReader(csvfile, delimiter='\t')
        for r in reader:
            if r['coll_man'] in identifier_ark.keys():
                update_sql += "UPDATE {0} SET {1}='{2}' WHERE {3}='{4}'\n".format(TABLE, LINK, identifier_ark[r[IDENTIFIER]], ID, r[ID])
            else:
                print(r['coll_man']+' is not in ArchivesSpace')

    print(update_sql);