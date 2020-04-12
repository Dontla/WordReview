from django.shortcuts import render, redirect, HttpResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q

from apps.review.models import Review, BookList, Words, Books

from apps.src.util import ormToJson, valueList
import config
from apps.review.src.init_db import init_db, update_db


from datetime import datetime, timedelta

EBBINGHAUS_DAYS = [1, 2, 4, 7, 15, 30]
EBBINGHAUS_DELTA = [0, 1, 2, 3, 8, 15]


def index(request):
    return render(request, "review.pug")


def temp(request):
    # out = Words.objects.filter(word__icontains='amiable')
    # for w in out:
    #     print(w.word, ".")
    #     print(w.word.count(' '))
    #     print(w.id)
    # print(out)
    update_db(Words)
    # if config.init_db_mode:
    #     from apps.review.src.init_db import (
    #         import_word, init_db_words, init_db_booklist, init_db_books)
    #     init_db_books(Books)
    #     import_word(Review, BookList, Words)
    #     init_db_words(Review, Words)
    #     init_db_booklist(BookList, Review)
    #     return HttpResponse('数据库初始化结束，请记得去 config.py 中将 init_db_mode 变量改为 Flase！')
    # else:
    #     return HttpResponse('如果需要导入数据库，请去 config.py 中将 init_db_mode 变量改为 True。\n平时请不用访问这个网址')
    return render(request, "homepage.pug")


def import_db(request):
    if request.method == 'POST':
        post = request.POST
        print(post)
        BOOK = post.get('BOOK')
        BOOK_zh = post.get('BOOK_zh')
        BOOK_abbr = post.get('BOOK_abbr')
        excel_path = post.get('excel_path')
        try:
            begin_index = int(post.get('begin_index'))
            if begin_index not in [0, 1]:
                return render(request, "import_db.pug", {'message': '请输入 0 或 1！'})
        except:
            return render(request, "import_db.pug", {'message': '请输入 0 或 1！'})
        print(BOOK, BOOK_zh, BOOK_abbr, begin_index,
              excel_path)
        try:
            init_db(BOOK, BOOK_zh, BOOK_abbr, begin_index,
                    excel_path, Books, Review, BookList, Words)
        except Exception as e:
            return render(request, "import_db.pug", {'message': e})
        return redirect('/review')
    return render(request, "import_db.pug")


@csrf_exempt
def review_lists(request):
    '''接口：复习完成 list，更新 book_list'''
    post = request.POST
    today = datetime.now() - timedelta(hours=4)  # 熬夜情况
    today_str = today.strftime('%Y-%m-%d')

    LISTS = [int(i) for i in post.get('list').split('-')]
    if len(LISTS) == 2:
        LISTS = list(range(LISTS[0], LISTS[1]+1))
    BOOK = post.get('book')

    msg = 'done'
    status = 200
    for LIST in LISTS:
        try:
            ld = Review.objects.filter(BOOK=BOOK, LIST=LIST)  # list data
            L_db = BookList.objects.get(BOOK=BOOK, LIST=LIST)
        except Exception as e:
            msg = f'获取数据异常：{e}'
            status = 501
            break

        rate = sum([r[0] if r[0] != -1 else 1 for r in ld.values_list('rate')
                    ]) / len(ld)
        rate = 1 - rate if rate != 0.0 else 0

        if rate == 0:
            status = 404
            msg = '你怕是还没背过这个List'
            continue

        L_db.word_num = len(ld)
        L_db.unlearned_num = len(Review.objects.filter(
            BOOK=BOOK, LIST=LIST, flag__lt=1))
        L_db.review_word_counts = ';'.join(
            set([str(t[0]) for t in ld.values_list('total_num')]))

        L_db.list_rate = rate
        # 计算近期记忆率
        recent_history = ''
        for word in ld:
            recent_history += word.history[-2:]
        L_db.recent_list_rate = recent_history.count('1') / len(recent_history)

        # 艾宾浩斯时间处理
        if 0 < L_db.ebbinghaus_counter < len(EBBINGHAUS_DELTA):
            c = L_db.ebbinghaus_counter
            should_next_date = datetime.strptime(L_db.last_review_date, '%Y-%m-%d'
                                                 ) + timedelta(days=EBBINGHAUS_DELTA[c])
            # print(should_next_date)
            if (today - should_next_date).days >= 0:
                # 今天 不早于 理论下一天
                L_db.ebbinghaus_counter += 1
                L_db.review_dates += ';' + today_str
                L_db.last_review_date = today_str
        elif L_db.ebbinghaus_counter == 0:
            L_db.last_review_date = today_str
            L_db.ebbinghaus_counter = 1
            L_db.review_dates = today_str
        else:
            print('这个 list 背完了')

        try:
            L_db.save()
        except Exception as e:
            msg = f'保存数据异常：{e}'
            status = 502
            break
        # data = {'msg': msg, 'status': 200}
    # except Exception as e:
    #     data = {'msg': e, 'status': 500}
    data = {'msg': msg, 'status': status}
    return JsonResponse(data)


@csrf_exempt
def update_note(request):
    '''接口：更新单词note'''
    post = request.POST
    msg = 'done'
    status = 200
    try:
        print(post)
        word = Words.objects.get(word=post.get('word'))
        word.note = post.get('note')
        word.save()
    except Exception as e:
        msg = e
        status = 501
    data = {'msg': msg, 'status': status}
    return JsonResponse(data)


@csrf_exempt
def update_word_flag(request):
    '''接口：更新单词flag'''
    post = request.POST
    msg = 'done'
    status = 200
    try:
        # print(post)
        words = [
            Review.objects.get(
                word=post.get('word'), LIST=post.get('list'), BOOK=post.get('book')),
            Words.objects.get(word=post.get('word'))
        ]
        for word in words:
            # print(word)
            word.flag = post.get('flag')
            word.save()
    except Exception as e:
        msg = e
        status = 501
    data = {'msg': msg, 'status': status}
    return JsonResponse(data)


@csrf_exempt
def review_a_word(request):
    '''接口：在数据库更新单词记忆情况'''
    post = request.POST
    try:
        word_in_list = Review.objects.filter(
            word=post.get('word'), BOOK=post.get('book'), LIST=post.get('list'))[0]
        word = Words.objects.get(word=post.get('word'))
    except Exception as e:
        return JsonResponse({'msg': '数据库损坏！' + e, 'status': 500})

    if (post.get('note') != 'false'):
        word.note = post.get('note')

    if post.get('repeat') == 'true':
        word_dbs = [word]
    else:
        word_dbs = [word, word_in_list]
    # print(post.get('word'), post.get('repeat'), word_dbs)

    for w in word_dbs:
        w.total_num += 1
        if post.get('remember') == 'true':
            w.history += '1'
        elif post.get('remember') == 'false':
            w.history += '0'
            w.forget_num += 1
        w.rate = word.forget_num / word.total_num
        w.save()
    data = {'msg': 'done', 'status': 200}
    return JsonResponse(data)


def get_word(request):
    '''接口：获取单词'''
    BOOK = request.GET.get('book')
    LIST = request.GET.get('list')
    LIST_li = [int(i) for i in LIST.split('-')]
    sortType = ['乱序', '记忆序']
    if len(LIST_li) == 1:
        list_info = Review.objects.filter(LIST=LIST, BOOK=BOOK, flag__lt=1)
        counter = BookList.objects.get(LIST=LIST, BOOK=BOOK).ebbinghaus_counter
        if counter == 0:
            sortType = ['顺序']
    elif len(LIST_li) == 2:
        list_info = Review.objects.filter(LIST__range=LIST_li, BOOK=BOOK)
    else:
        raise KeyError('LIST_li 长度异常')

    pankeys = {
        'total_num': 'panTotalNum',
        'forget_num': 'panForgetNum',
        'rate': 'panRate',
        'history': 'panHistory',
    }

    list_info = ormToJson(list_info)
    for l in list_info:
        l = l['fields']
        try:
            w = ormToJson([Words.objects.get(word=l['word'])])[0]['fields']
        except Words.DoesNotExist:
            return JsonResponse({"msg": f"Word not found:{l['word']}", 'status': 404})

        for old, pan in pankeys.items():
            w.update({pan: w.pop(old)})
        l.update(w)

    data = {
        'data': list_info,
        'status': 200,
        'sort': sortType,
        'begin_index': int(Books.objects.get(BOOK=BOOK).begin_index == 0),
    }
    return JsonResponse(data)


def get_calendar_data(request):
    '''接口：获取日历渲染数据'''
    books = Books.objects.all()
    book_info = {}
    for b in books:
        book_info[b.BOOK] = {
            'abbr': b.BOOK_abbr,
            'begin_index': 1 if b.begin_index == 0 else 0,
        }
    # db = BookList.objects.filter(~Q(ebbinghaus_counter=0))
    db = BookList.objects.filter(ebbinghaus_counter__range=[1, 6])
    data = ormToJson(db)
    for d in data:
        d = d['fields']
        d['abbr'] = book_info[d['BOOK']]['abbr']
        d['begin_index'] = book_info[d['BOOK']]['begin_index']

    data = {
        'data': data,
        'EBBINGHAUS_DELTA': EBBINGHAUS_DELTA,
        'status': 200,
    }
    return JsonResponse(data)


def review(request):
    '''页面：单词复习页'''
    LIST = request.GET.get('list')
    BOOK = request.GET.get('book')
    if LIST is None or BOOK is None:
        # if LIST is None:
        #     LIST = 0
        # if BOOK is None:
        #     BOOK = 'qugen10000'
        return redirect(f'/review/review?list={LIST}&book={BOOK}')
    return render(request, "review.pug", locals())


def calendar(request):
    '''页面：艾宾浩斯日历图'''
    return render(request, "calendar.pug", )


def homepage(request):
    '''页面：复习主页'''
    # BOOK = request.GET.get('book')
    # if BOOK is None:
    #     BOOK = 'qugen10000'
    books = Books.objects.all()[::-1]
    dic = {}
    for b in books:
        dic[b.BOOK] = {
            'BOOK_zh': b.BOOK_zh,
            'begin_index': b.begin_index,
        }
    data = []
    for BOOK, book_info in dic.items():
        book = book_info['BOOK_zh']
        index = book_info['begin_index']
        # index = 1 if index == 0 else 0
        lists = sorted([l[0] for l in (set(Review.objects.filter(
            BOOK=BOOK).values_list('LIST')))])
        list_info = []
        for l in lists:
            try:
                ld = BookList.objects.get(BOOK=BOOK, LIST=l)
            except Exception as e:
                print(l, e)
                continue
            if ld.unlearned_num == -1:
                L = ld.word_num
                del_L = 0
            else:
                L = ld.unlearned_num
                del_L = ld.word_num - ld.unlearned_num
            # total = sorted([int(i) for i in ld.review_word_counts.split(';')])
            list_info.append({
                'i': l,
                'len': L,
                'del_len': del_L,
                'rate': int(ld.list_rate * 100),
                'recent_rate': int(ld.recent_list_rate * 100),
                # 'min': min(total),
                # 'max': max(total),
                'times': ld.ebbinghaus_counter,
                'index': index
            })
        data.append({
            'name': book,
            'name_en': BOOK,
            'lists': list_info,
        })

    return render(request, "homepage.pug", locals())
