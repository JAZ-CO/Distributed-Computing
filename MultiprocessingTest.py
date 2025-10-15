# -*- coding: utf-8 -*-
"""
Created on Fri Nov 16 20:12:23 2018

@author: DR.AYAZ
"""

from mpi4py import MPI

comm = MPI.COMM_WORLD
rank = comm.Get_rank() # MPI.COMM_WORLD.Get_rank(): process id within the MPI communicator starting from 0,1,2,3.......
size = comm.Get_size() # Number of Processes in the MPI communicator
print('My rank is ',rank)
print('Number of Processes = ', size)