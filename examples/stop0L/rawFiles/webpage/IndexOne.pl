#!/usr/bin/perl

use Cwd;
# Revision history:
# 12 March 2012 DGC   Fairly major revision of code (but not of algorithm)
$debugmcolautt=3;


$dir=getcwd;
if ($#ARGV<0 || "$ARGV[0]" eq "-h") {
    print "\n";
    print "Purpose: run webpage making script on one note or paper \n\n";
    print "Syntax: ./IndexOne.pl [type] [paper/note]\n";
    print "  where [type] is e.g. CONFNOTES, PAPERS, PUBNOTES, DRAFTS, PLOTS \n";
    print "  and [paper/note] is the directory where the plots are, e.g. HIGG-2012-01\n\n";
    exit 0;
} else {
    $refID=$ARGV[1];
    print "reference ID $refID \n";
}

$DevelopmentVersion=0 ;
$DevelopmentVersion=1 if $dir=~/dev/ ;  

print "version $DevelopmentVersion $0 $dir\n";

if ($DevelopmentVersion) {
    require "/afs/cern.ch/atlas/www/GROUPS/PHYSICS/Coord/confscripts/dev/ConfNoteLib.pl";
    $NoteFlavourList="PAPERS CONFNOTES PUBNOTES DRAFTS PLOTS" ;
}
else {
    require "/afs/cern.ch/atlas/www/GROUPS/PHYSICS/Coord/confscripts/ConfNoteLib.pl" ;
    $NoteFlavourList="PAPERS CONFNOTES PUBNOTES DRAFTS PLOTS" ;
}

print "$0 running at " . `/bin/date` ;

# if as argument the list is given it will use this (e.g. "CONFNOTES" or "PAPERS" ...) else it uses the default given above
if ($#ARGV>-1) {
    $NoteFlavourList="" ;
    foreach $a (@ARGV) {
        $a=uc($a) ;
        if (index($CNLAllKnownFlavours,$a) > -1) {
            $NoteFlavourList.=" " if $NoteFlavourList ne "" ;
            $NoteFlavourList.=$a ;
        }
    }
}

print "!!!!! Development version !!!!!\n" if $DevelopmentVersion;

# check if we are in the default production directory or in some private test directory
# and take actions accordingly
$defaultdir='/afs/cern.ch/atlas/www/GROUPS/PHYSICS/';
$private=0; # variable set depending if it is private test production or in official area
$mydir=$ENV{'PWD'};
$glancedir=$defaultdir."/Coord/glance";
if (index($mydir,$defaultdir)!=-1) {
    #process the table of CONFnotes to avoid line breaks etc.
    # do this only in official version
    $cmd="python /afs/cern.ch/atlas/www/GROUPS/PHYSICS/Coord/confscripts/format_csv.py /afs/cern.ch/user/a/atlaspo/twikirun/csv6646/table6646.csv $glancedir/table5505_fixed.csv"; 
    #    $cmd="python /afs/cern.ch/atlas/www/GROUPS/PHYSICS/Coord/confscripts/format_csv.py /afs/cern.ch/user/a/atlaspo/twikirun/csv5505/table5505.csv $glancedir/table5505_fixed.csv";
    system("$cmd");
} else {
    $private=1;
}
# BIG loop over flavour of the note...

foreach $NoteFlavour (split(' ',$NoteFlavourList)) {
    &InitialiseVariables($NoteFlavour,$private) ;
    print "Processing $NiceName (" ;

    # Note that GetNoteList *does* include embargoed notes
    $NoteList[0]=$refID;
    print $#NoteList . ")\n" ;


    # now we have a list of all notes/papers produced in ATLAS so far and will loop through them
    foreach $n (@NoteList) {
        if (-f "$NoteDirectory/$n/embargo"  && ! -f "$NoteDirectory/$n/.htaccess") {
            # DGC 18 July 2011 - if embargoed now use .htaccess protection but still write the index...
            # embargoed note - add a small .htaccess to restrict access to a-c-p 
            system("/bin/cp $NoteDirectory/template/.htaccess $NoteDirectory/$n/.htaccess") ;
            print "Adding .htaccess for a-c-p $n - embargoed note\n" ; 
            #     next ;
        }
        if ( -f "$NoteDirectory/$n/nopaper"  && ! -f "$NoteDirectory/$n/.htaccess") {
            # BH: add nopaper category to also be embargoed - add a small .htaccess to restrict access to a-c-p                                                       system("/bin/cp $NoteDirectory/template/.htaccess $NoteDirectory/$n/.htaccess") ;
            print "Adding .htaccess for a-c-p $n - embargoed papere\n" ;
        }

        $CDSValid=0 ;
        $InfoFileValid=0 ;
        $NoteDirectory = "/afs/cern.ch/atlas/www/GROUPS/PHYSICS/".$NoteFlavour;
        # for test purposes make a different directory
        $defaultdir='/afs/cern.ch/atlas/www/GROUPS/PHYSICS/';
        if (index($mydir,$defaultdir)<0) {
            $NoteDirectory = $mydir. "/".$NoteFlavour;
        } 
        print "directory of note: $NoteDirectory \n";
        # now see if directory exists        
        if (-f "$NoteDirectory/$n/$n.$InfoTag") {
            &ReadNoteInfo($n) ;
            $InfoFileValid=1 ;
        }
        if ($NoteFlavour eq "CONFNOTES"){ 
            if (0==0||!$InfoFileValid||!$CDSID) {
                $CDSValid=&QueryCDSForInfo($n) ;
            }
            $SSresult=&QueryGlanceForCONFInfo($n);
            if ($DevelopmentVersion>0 && $SSresult>0 ) {print "$n: found a superseding result @MySuperseders\n"};
        }        
        if ($NoteFlavour eq "PAPERS") {
            $GlanceValid=&QueryGlanceForInfo($n) ;
            if ($debugmcolautt > 0) { print "\nGlance valid = $GlanceValid\n"; }        
            print "got a paper in glance: $GlanceValid \n" if ($DevelopmentVersion>0);
            $test=&GetPaperAbstract($n);
            if ($debugmcolautt > 0) { print "\nTest = $test\n"; }        
        }
        if ($NoteFlavour eq "PUBNOTES"){ 
            print "it's a pubnote";
            if (!$InfoFileValid||!$CDSID) {
               $CDSValid=&QueryCDSForInfo($n) ;
            }
            $CDSValid = &QueryCDSForInfo($n);

            $SSresult=&QueryGlanceForPUBInfo($n);
            if ($DevelopmentVersion>0 && $SSresult>0 ) {print "$n: found a superseding result @MySuperseders\n"};
        }
        if ($NoteFlavour eq "UPGRADE") {
            $CDSValid=&QueryCDSForInfo($n) ;
        }
        if ($NoteFlavour eq "PLOTS") {
            $InfoFileValid=1;
        }

        if ($DevelopmentVersion ) {
            print "$n: info=$InfoFileValid cds=$CDSValid glance=$GlanceValid\n" ;
        }


        print ("InfoFileValid = $InfoFileValid\n");
        if ($InfoFileValid) {
            print "$NoteTitle / $NoteDate.\n" ;
            &FindNoteFiles($n) ;
            &MakeFigurePNGs($n) ;
            &MakeTablePNGs($n) ;
            &MakeFigureThumbnails($n) ;
            &MakeTableThumbnails($n) ;
            # for CONF notes we also make data files available if they exist (6/6/2013)    
            if ($NoteFlavour eq "CONFNOTES") {
                &MakeDataFiles($n);
            }       
        }
        if ($InfoFileValid || $CDSValid) {
            print "Writing index file for $n\n" if $DevelopmentVersion ;
            &WriteNoteIndex($n,$InfoFileValid,$CDSValid) ;
        }

        # delete .htaccess if it is there (actually rename)
        if ((!-f "$NoteDirectory/$n/embargo") && (!-f "$NoteDirectory/$n/nopaper") && -f "$NoteDirectory/$n/.htaccess") {
            print "Embargo lifted for $n - removing htaccess\n" ;
            system("/bin/mv $NoteDirectory/$n/.htaccess $NoteDirectory/$n/.dead_htaccess") ;
        }
        print "--------------------------------------------------------------------\n" ;
   }

    &WriteListOfNotes($NiceName,"CONF") if $NoteFlavour eq "CONFNOTES" ;
    &WriteListOfNotesEmbargoed($NiceName,"CONF") if $NoteFlavour eq "CONFNOTES" ;
    &WriteListOfNotesEmbargoed($NiceName,"PAPERS") if $NoteFlavour eq "PAPERS" ;
    #&WriteListOfNotes($NiceName,"PAPERS") if $NoteFlavour eq "PAPERS" ;
    #   &WriteListOfNotes($NiceName,"PUB") if $NoteFlavour eq "PUBNOTES" ;
}

print "$0 completed at " . `/bin/date` ;

exit 0 ;
