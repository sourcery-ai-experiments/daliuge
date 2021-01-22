#
#    ICRAR - International Centre for Radio Astronomy Research
#    (c) UWA - The University of Western Australia, 2017
#    Copyright by UWA (in the framework of the ICRAR)
#    All rights reserved
#
#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; either
#    version 2.1 of the License, or (at your option) any later version.
#
#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this library; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston,
#    MA 02111-1307  USA
#
"""
Tests the low-level functionality for drops to hash runtime data.
"""

import unittest

from dlg.common.reproducibility.constants import ReproducibilityFlags
from dlg.common.reproducibility.reproducibility import common_hash
from dlg.ddap_protocol import DROPStates
from dlg.drop import AbstractDROP
from merklelib import MerkleTree


class RerunHashTests(unittest.TestCase):
    def test_null_merkleroot(self):
        """
        Sanity check that the default MerkleRoot of an abstract drop is Null
        Consider it a cardinal sin to change this.
        """
        a = AbstractDROP('a', 'a')
        self.assertIsNone(a.merkleroot)

    def test_generate_rerun_data(self):
        """
        Tests that completed Rerun data contains the completed flag.
        """
        a = AbstractDROP('a', 'a')
        a.reproducibility_level = ReproducibilityFlags.RERUN
        a.setCompleted()
        self.assertTrue(a.generate_rerun_data(), [DROPStates.COMPLETED])

    def test_commit_on_complete(self):
        """
        Tests that merkle_data is generated upon set_complete status and is correct (NOTHING, RERUN)
        """

        a = AbstractDROP('a', 'a')
        b = AbstractDROP('b', 'b')
        a.reproducibility_level = ReproducibilityFlags.RERUN
        b.reproducibility_level = ReproducibilityFlags.NOTHING
        self.assertIsNone(a.merkleroot)
        self.assertIsNone(b.merkleroot)

        # Test RERUN
        a.setCompleted()
        test = MerkleTree({'status': DROPStates.COMPLETED}.items(), common_hash)
        # 689fcf0d74c42200bef177db545adc43c135dfb0d7dc85b166db3af1dcded235
        self.assertTrue(test.merkle_root == a.merkleroot)

        # Test NOTHING
        b.setCompleted()
        # None
        self.assertIsNone(b.merkleroot)
        self.assertTrue(b._committed)

    def test_recommit(self):
        """
        Should raise an exception preventing a straight-recommit.
        """
        a = AbstractDROP('a', 'a')
        a.reproducibility_level = ReproducibilityFlags.RERUN
        a.setCompleted()
        with self.assertRaises(Exception):
            a.commit()

    def test_set_reproducibility_level(self):
        """
        Tests functionality for changing a DROP's reproducibility flag
        If already committed. The drop should reset and re-commit all reproducibility data
        If not committed, the change can proceed simply.
        """
        a = AbstractDROP('a', 'a')
        b = AbstractDROP('b', 'b')
        a.reproducibility_level = ReproducibilityFlags.NOTHING
        b.reproducibility_level = ReproducibilityFlags.NOTHING

        a.setCompleted()
        self.assertIsNone(a.merkleroot)
        a.reproducibility_level = ReproducibilityFlags.RERUN
        a.commit()
        self.assertIsNotNone(a.merkleroot)

        self.assertIsNone(b.merkleroot)
        b.reproducibility_level = ReproducibilityFlags.RERUN
        b.setCompleted()
        self.assertIsNotNone(b.merkleroot)

        with self.assertRaises(TypeError):
            a.reproducibility_level = 'REPEAT'
