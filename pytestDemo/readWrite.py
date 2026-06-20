file=open('test.txt')

#read all the contents of file
#print(file.read())

#read n numbers of characters the contents of file
#print(file.read(2))

#print one single line at  a time
#print(file.readline())
#print(file.readline())

#print single line by line at  a time
#line = file.readline()
#while line!="":
#    print(line)
#    line=file.readline()


for line in file.readlines():
    print(line)

file.close()
