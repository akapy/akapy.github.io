#!/usr/local/bin/perl
# $Id: kuttukibbs.cgi,v 1.12 2004/12/15 14:09:58 yto Exp $
use strict;

### 編集して下さい
my $conf_file = "/home/akapy/kuttukibbs/kuttukibbs.conf"; # ユーザ設定ファイルの場所

### ユーザ設定項目 (kuttukibbs.conf で設定できます)
my $log_dir = "kblog";		# コメントログファイルを置くディレクトリ
my $latest_comment_display_num = 20; # 最新投稿表示のときに一度に表示する数
my $kb_js_display_max = 5;	# 表示するコメントの数 for js
my $kb_js_strlen_max = 40;	# 1 コメントが表示される文字数 for js
my $admin_log_file = "kblog/log.txt"; # 管理者用ログファイル
my $passwd = "akapy";		# 管理者用パスワード
my $noname = "???";		# デフォルトの投稿者名
my $page_template_default;
my $page_template_latest;
my $page_template_edit;
my $charset = "EUC-JP";		# 文字コード

# RSS 関連変数
my $rdf_file;		# 出力する RSS のファイル名
my $rdf_content;
my $rdf_dcdate;
my $rdf_url;
my $rdf_id;
my $rdf_all_template;
my $rdf_seq_template;
my $rdf_item_template;

### グローバル変数
my $latest_id = -1;		# 最新のコメントの ID
my %com_hash;			# コメントを格納するハッシュ
my $URLCHARS = "[-_.!~*'a-zA-Z0-9;/?:@&=+,%\#\$]";


# ユーザ設定ファイルの読み込み
if (not -e $conf_file) {
    print "error: can't read $conf_file\n";
    exit;
}
open(CONF, "$conf_file") or die "can't open $conf_file : $!";
my $conf = join('', <CONF>);
eval $conf;

# 現在時刻の獲得
use POSIX qw(strftime);
my $what_time_is_it_now = strftime "%Y-%m-%d %H:%M:%S", localtime;

use CGI;
my $q = new CGI;
#print $q->Dump;

my $mode = $q->param('mode');

# ユーザ情報
my $name = $q->param('name');
my $mail_or_url = $q->param('mail');
my $body = $q->param('body');

# header
if ($mode eq 'write') {
    escape_string(\$name);	
    escape_string(\$mail_or_url);	
    my $cookie = $q->cookie(-name=>'kuttukibbs', 
			    -value=>"$name\t$mail_or_url", 
			    -expires=>'+30d');
    print $q->header(-cookie=>$cookie, -charset=>$charset);
} else {
    print $q->header(-charset=>$charset);
    if (defined $q->cookie('kuttukibbs')) {
	($name, $mail_or_url) = split(/\t/, $q->cookie('kuttukibbs')); 
    }
    escape_string(\$name);	
    escape_string(\$mail_or_url);	
}

my $cgi_url = $q->url();

my $comments;
my $page_html;


if ($mode eq 'latest') {output_latest();}

# コメント対象の情報
my $logid = $q->param('id'); # コメントの ID。ログファイル指定に利用
$logid =~ s{[^a-zA-Z0-9\.\-\#_]}{_}g;
exit if ($logid =~ /^\s*$/);
my $target_url = id2url($logid); # コメント対象の URL
$cgi_url .= "?id=$logid";
my $fn_pref = "$log_dir/$logid";

### 読み込み
my $fn = "$fn_pref.log";
my $all;
read_file($fn, \$all);

if ($mode eq "edit") {
    my $co = $q->param('content');
    if (defined $co) {
	my $pw = $q->param('passwd');
	if (defined $pw and $pw ne "" and $pw eq $passwd) { 
	    rename $fn, $fn."~";
	    save_file($fn, \$co);
	    read_file($fn, \$all);
	    set_comment_hash(\%com_hash, \$all);
            write_to_jsfile($fn_pref.".js"); # JavaScript Feed ファイル
            write_to_rssfile(); # RSS ファイル
            %com_hash = ();
	} else {
	    print "wrong password!\n";
	}
    } else {
	my $content = $all;
	$content =~ s/&/&amp;/g;
	eval qq(\$page_html = << "FFF"\n$page_template_edit\nFFF\n);
	print $page_html;
	exit;
    }
}

set_comment_hash(\%com_hash, \$all);

### 書き込み
if ($mode eq "write") {
    $name = $noname if ($name =~ /^\s*$/sm);

##### スパム対策 2006/08/19
##### http://www.pochi.cc/~sasaki/chalow/2006-01-25-2.html
# anti spam
    if (($body ne "") && ($body !~ m/[\x80-\xff]/)) {die('error')};
#####
    
    if ($body !~ /\A\s*\Z/m) {
	escape_string(\$name);	
	escape_string(\$mail_or_url);	
	escape_string(\$body);

	$body =~ s/\r?\n/<br>/gsm;
	
	my $name_tmp = $name;
	if ($mail_or_url =~ /^http:\/\/$URLCHARS+$/) {
	    $name_tmp = qq(<a href="$mail_or_url">$name</a>);
	}
	
	$latest_id++;
	$com_hash{$latest_id}{n} = $name_tmp;
	$com_hash{$latest_id}{m} = $body;
	$com_hash{$latest_id}{d} = $what_time_is_it_now;

##### スパム対策 2006/08/25
#exit if (length($body) > 250); # spam
exit if (length($body) > 95); # spam
#####	

	write_to_logfile();	# ログファイルへの書き込み
	write_to_jsfile($fn_pref.".js"); # JavaScript Feed ファイルへの書き込み
	write_to_rssfile(); # RSS ファイルへの書き込み
	write_to_adminlogfile(); # 管理者用ログファイルへの書き込み
    }
}

### 表示
for (my $i = $latest_id; $i >= 0; $i--) {
    next unless defined $com_hash{$i};
    $comments .= make_comment_html($com_hash{$i}, $i + 1);
}

eval qq(\$page_html = << "FFF"\n$page_template_default\nFFF\n);
print $page_html;
exit;

#----------------------------------------------------------------------

###
sub escape_string {
    my ($sp) = @_;
    $$sp =~ s/</&lt;/g;
    $$sp =~ s/>/&gt;/g;
    $$sp =~ s/\"/&quot;/g;	# "
}


### ファイルを読む
sub read_file {
    my ($fn, $strp) = @_;
#    if (-e $fn and -s $fn != 0) {
    if (-e $fn) {
	open(F, $fn) or die "can't open $fn : $!\n";
	$$strp = join('', <F>);
	close(F);
    }
}

### ファイルをセーブ
sub save_file {
    my ($fn, $strp) = @_;
    open(F, "> $fn") or die "can't open $fn : $!\n";
    flock(F, 2);
    print F $$strp;
    close F;
}

### コメントログファイルを解析し、各コメントごとに hash に格納する。
sub set_comment_hash {
    my ($hashp, $allp) = @_;
    foreach (split(/\r?\n/, $$allp)) {
	if (/^([nmd])\[(\d+)\] = "(.*?)";$/) {
	    $hashp->{$2}{$1} = $3;
	    $latest_id = $2 if ($latest_id < $2);
	}
    }
}


### コメント出力用 HTML を作る。
sub make_comment_html {
    my ($commentp, $commentid) = @_;
    my $mes = $commentp->{'m'};
    $mes =~ s{((s?https?|ftp)://($URLCHARS+))}{<a href="$1">$1</a>}g;

    my $anchor = qq(<span class="canchor">*</span>);
    my $page_info = "";
    if (defined $commentp->{i}) {
	my $id = $commentp->{i};
	my $url = id2url($id);
	my $bbs_url = "$cgi_url?id=$id";
	$page_info = qq(<span class="page">[<a href="$url">$url</a>, 
			<a href="$bbs_url">BBS</a>]</span>);
    } else {
	$anchor = qq(<a name="$commentid" href="$cgi_url\#$commentid">
		     <span class="canchor">*</span></a>);
    }
    my $rv .= << "DAY"
<div class="acomment">
<div class="commentator">
$anchor
<span class="commentator">$$commentp{'n'}</span>
<span class="commenttime">$$commentp{'d'}</span>
$page_info
</div>
<p>$mes</p>
</div>
DAY
    ;
    return $rv;
}


### ログファイルへの書き込み
sub write_to_logfile {
    my $fn = "$fn_pref.log";
    my $str;
    foreach (sort {$a <=> $b} keys %com_hash) {
	$str .= qq(n[$_] = "$com_hash{$_}{n}";\nm[$_] = "$com_hash{$_}{m}";
d[$_] = "$com_hash{$_}{d}";\n);
    }
    save_file($fn, \$str);
}


### JavaScript Feed ファイルへの書き込み
sub write_to_jsfile {
    my ($jsfn) = @_;
#    my $jsfn = "$fn_pref.js";
    my $str = "";
    my $cnt = $kb_js_display_max;
    for (my $i = $latest_id; $i >= 0; $i--) {
	next unless defined $com_hash{$i};

	my ($n,$m,$d)  = ($com_hash{$i}{n},$com_hash{$i}{m},$com_hash{$i}{d});
	$n =~ s/^(.{1000}).*$/$1/;
	$m =~ s/<br>//ig;	# 改行タグは削除

	$n =~ s/\\/\\\\/g;
	$m =~ s/\\/\\\\/g;

	$n =~ s/\'/\\'/g;
	$m =~ s/\'/\\'/g;

	# 文字多いときの末尾カット - charsetにより問題あるかも
	if ($m =~ s/^(([\x80-\xff].|[\x00-\x7f]){$kb_js_strlen_max}).*$/$1/) {
	    $m =~ s/((s?https?|ftp):\/\/$URLCHARS+)$/$2/;
	    $m .= "...";
	}
	# URL to anchor
	$m =~ s/((s?https?|ftp):\/\/$URLCHARS+)/<a href="$1">$1<\/a>/ig;

	$str .= << "JS";
document.writeln('<p><span class="canchor">_</span>');
document.writeln('<span class="commentator">$n</span>');
document.writeln(' [$m]</p>');
JS
    ;

	$cnt--;
	last if ($cnt <= 0);
    }
    if ((keys %com_hash) > $kb_js_display_max) {
	$str .= << "JS";
document.writeln('<p><span class="canchor">_</span>');
document.writeln('<span class="commentator">...</span></p>');
JS
    ;
    }

    save_file($jsfn, \$str);
}


### 管理者用ログファイルへの書き込み
sub write_to_adminlogfile {
    my $str = "remote_host: ". $q->remote_host(). "\n";
    $str .= "id: $logid\n";
    $str .= "mail or url: $mail_or_url\n";
    $str .= << "ADD";		# 追加内容
n[$latest_id] = "$name";
m[$latest_id] = "$body";
d[$latest_id] = "$what_time_is_it_now";

ADD
    ;
    open(F, ">> $admin_log_file") or die "can't open $admin_log_file : $!\n";
    flock(F, 2);
    print F $str;
    close(F);
}


### 最近投稿されたコメントを得る
sub get_latest {
    my @fl = <$log_dir/*.log>;
    my @lalist;
    foreach my $f (@fl) {
	open(F, $f) or die "$! $f";
	next if (-s $f == 0);
	my $all = join('', <F>);
	my %hash;

	my ($id) = ($f =~ /([^\/]+)\.log$/);
	set_comment_hash(\%hash, \$all);
	foreach my $i (keys %hash) {
	    push @lalist, {d => $hash{$i}{'d'}, m => $hash{$i}{'m'},
			   n => $hash{$i}{'n'}, i => $id};
	}
	@lalist = (sort {$b->{d} cmp $a->{d}}
		   @lalist)[0..($latest_comment_display_num - 1)];
    }
    foreach my $i (@lalist) {
	last if ($i eq "" || $$i{'i'} eq "");
	$comments .= make_comment_html($i, 0);
    }
    return @lalist;
}

### 最近投稿されたコメントを表示
sub output_latest {
    my @lalist = get_latest();

    $cgi_url .= "?mode=latest";

    eval qq(\$page_html = << "FFF"\n$page_template_latest\nFFF\n);
    print $page_html;
    exit;
}

### RSS で出力
sub write_to_rssfile {
    my @lalist = get_latest();
    my $rdf_seq;
    my $rdf_item;

    foreach my $i (@lalist) {
        last if ($i eq "" || $$i{'i'} eq "");
        my $date = $$i{'d'};
        my $id = $$i{'i'};
        my $url = id2url($id);
        my $desc = $$i{'n'} . " [" . $$i{'m'}. "]";
        my $seqtmp;
        my $itemtmp;

        $date =~ s/(\d\d\d\d)-(\d\d)-(\d\d)\s(\d\d):(\d\d):(\d\d)/$1-$2-$3T$4:$5:$6+09:00/;

        my $cont_max_len = 300;
        if (length($desc) > $cont_max_len) {
            $desc =~ s/^(.{$cont_max_len}).*$/$1/sm;
            $desc =~ s/\n[^\n]*$//;
            $desc .= "...";
        }

        $desc =~ s|<[^<>]+?>||gosm;
        $desc =~ s/&/&amp;/go;
        $desc =~ s/>/&gt;/go;
        $desc =~ s/</&lt;/go;
        $desc =~ s/"/&quot;/go; # ";
        $desc =~ s/\t//g;

        $rdf_content = $desc;
        $rdf_dcdate = $date;
        $rdf_url = $url;
        $rdf_id = $id;

        eval qq(\$seqtmp = << "FFF"\n$rdf_seq_template\nFFF\n);
        eval qq(\$itemtmp = << "FFF"\n$rdf_item_template\nFFF\n);

        $rdf_seq .= $seqtmp;
        $rdf_item .= $itemtmp;
    }
    $rdf_dcdate = strftime "%Y-%m-%dT%H:%M:%S+09:00", localtime;
    my $rdf;
    eval qq(\$rdf = << "FFF"\n$rdf_all_template\nFFF\n);

    save_file($rdf_file, \$rdf);
}

